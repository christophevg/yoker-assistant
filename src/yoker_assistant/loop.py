"""The main email-polling loop.

Polls an IMAP inbox for UNSEEN messages, hands each to the yoker assistant
agent (resolved by name from the plugin registry via :class:`yoker.Session`)
as a From/Subject/Date/body payload, and branches on the agent's reply:

  1. ``{{NO_REPLY}}`` sentinel  → intentional silence: mark read + archive.
  2. empty/whitespace reply     → transient problem: leave UNSEEN for retry.
  3. unsafe HTML (guard failure) → mark read (no archive) + plain-text notice
     to the original sender.
  4. valid HTML reply           → send reply + mark read + archive.

``build_message`` is a plain function (P2-006, per owner instruction). No
``handoff.py`` module, no wrapper classes — the loop drives ``Session.agent``
and calls ``IMAPClient`` / ``SMTPClient`` directly.
"""

import asyncio
import logging
import re
from email.utils import parseaddr
from signal import SIGINT, SIGTERM
from typing import Any

from simple_email_gw import IMAPClient, SMTPClient, get_pool
from simple_email_gw.config import get_recipient_whitelist
from yoker.config import get_yoker_config
from yoker.core import Agent
from yoker.session import Session

logger = logging.getLogger(__name__)

NO_REPLY_SENTINEL = "{{NO_REPLY}}"
_INITIALIZE_PROMPT = "Initialize"
_POLL_INTERVAL = 60  # seconds between polls when inbox is empty
_INBOX_FOLDER = "INBOX"
_ARCHIVE_FOLDER = "Archive"
# The pool resolves account configuration from the SDK's ServerConfig; the
# loop only knows the account name (the SDK's default convention).
_ACCOUNT_NAME = "default"

_UNSAFE_TAGS = ("<script", "<style", "<img", "<iframe", "<object", "<embed", "<form")
_UNSAFE_HANDLER = re.compile(r"\son\w+\s*=")


def _contains_unsafe_html(html: str) -> bool:
  """Guardrail: True if agent output contains unsafe HTML tags or event handlers."""
  lowered = html.lower()
  if any(tag in lowered for tag in _UNSAFE_TAGS):
    return True
  return bool(_UNSAFE_HANDLER.search(html))


def build_message(email_message: dict[str, Any]) -> str:
  """Build the handoff payload from a raw simple_email_gw message dict.

  Pure function, no I/O. Produces From/Subject/Date headers + body. CR/LF is
  collapsed in header values to prevent handoff-format injection; the body is
  passed through verbatim.
  """

  def _clean(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ")

  from_ = _clean(email_message.get("from", ""))
  subject = _clean(email_message.get("subject", ""))
  date_ = _clean(email_message.get("date", ""))
  body = str(email_message.get("body", ""))
  return f"From: {from_}\nSubject: {subject}\nDate: {date_}\n\n{body}"


async def _process_one(
  imap: IMAPClient,
  smtp: SMTPClient,
  agent: Agent,
  message_id: str,
) -> None:
  """Process a single incoming message through the four-way branching."""
  msg = await imap.fetch_message(message_id, _INBOX_FOLDER)
  handoff = build_message(msg)

  logger.info("=== Incoming message (user turn) ===")
  logger.info(handoff)

  reply_html = await agent.process(handoff)

  logger.info("=== Agent reply ===")
  logger.info(reply_html if reply_html.strip() else "(empty — no reply)")

  sender = parseaddr(msg.get("from", ""))[1]
  subject = msg.get("subject", "")
  in_reply_to = msg.get("message_id", "")

  if NO_REPLY_SENTINEL in reply_html:
    # Branch 1: intentional no-reply → mark read + archive.
    await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    await imap.move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)
  elif not reply_html.strip():
    # Branch 2: empty/whitespace → transient problem → leave UNSEEN for retry.
    logger.info("agent returned empty reply; leaving UNSEEN", extra={"message_id": message_id})
  elif _contains_unsafe_html(reply_html):
    # Branch 3: guard failure → mark read (no archive) + reply notice to sender.
    await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    notice = (
      "The assistant was unable to produce a safe reply to your message. "
      "Your message was received but no reply will be sent. "
      "If you believe this is an error, please try again later."
    )
    await smtp.reply_email(
      to=sender,
      subject=f"Re: {subject}",
      body=notice,
      in_reply_to=in_reply_to,
    )
  else:
    # Branch 4: valid reply → send + mark read + archive.
    await smtp.reply_email(
      to=sender,
      subject=f"Re: {subject}",
      body="",
      html_body=reply_html,
      in_reply_to=in_reply_to,
    )
    await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    await imap.move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)


async def run(once: bool = False) -> None:
  """The main loop. Constructs a yoker ``Session`` once, polls IMAP, processes messages.

  The assistant agent is resolved by name (``yoker_assistant:assistant``)
  from the Session's plugin-loaded :class:`AgentRegistry`, replacing the
  former bare-``Agent`` + ``_load_assistant_definition`` construction. The
  entire loop body lives inside the ``async with Session`` block so the
  Session owns the agent registry, the ``agent`` tool, and clean shutdown.

  Refuses to start when the recipient whitelist is disabled (C1 blocking fix):
  the whitelist fails open, so an unset whitelist would let the assistant reply
  to arbitrary senders. Account/credentials configuration is delegated to
  Simple Email GW's ``ConnectionPool`` via the ``"default"`` account name.
  """
  # C1 BLOCKING FIX: refuse to run if the recipient whitelist is disabled.
  if not get_recipient_whitelist().enabled:
    raise RuntimeError(
      "Recipient whitelist is disabled — refusing to run (fails open). "
      "Set EMAIL_RECIPIENT_DOMAINS, EMAIL_RECIPIENT_ADDRESSES, "
      "or EMAIL_RECIPIENT_WHITELIST_JSON to enable outgoing reply safety."
    )

  config = get_yoker_config()
  config.agent = "yoker_assistant:assistant"

  async with Session(config, session_id="yoker-assistant") as session:
    agent = session.agent

    # One-time session-setup turn (§4.1).
    await agent.process(_INITIALIZE_PROMPT)

    # The pool reads the EMAIL_* env vars via ServerConfig and caches clients.
    # Returned clients are NOT yet connected — the loop connects per iteration.
    pool = await get_pool()
    imap = await pool.get_imap_client(_ACCOUNT_NAME)
    smtp = await pool.get_smtp_client(_ACCOUNT_NAME)  # fire-and-forget per send

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (SIGINT, SIGTERM):
      try:
        loop.add_signal_handler(sig, stop.set)
      except NotImplementedError:
        # Windows — signal handlers not supported on this event loop.
        pass

    # Connect/disconnect bookend each iteration. The poll interval is several
    # minutes, so holding a connection open across the sleep would just time
    # out server-side. The first iteration's connect is the credential check.
    while not stop.is_set():
      await imap.connect()
      try:
        uids = await imap.search(_INBOX_FOLDER, "UNSEEN")
        for mid in uids:
          if stop.is_set():
            break
          try:
            await _process_one(imap, smtp, agent, mid)
          except Exception:
            # §7: per-message exceptions are logged and skipped. The message
            # stays UNSEEN (not marked read) → retried next iteration.
            logger.exception("per-message failure; leaving UNSEEN", extra={"message_id": mid})
            continue
      finally:
        try:
          await imap.disconnect()
        except Exception:
          logger.exception("imap disconnect failed")

      if once:
        break
      if not uids:
        try:
          await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL)
        except asyncio.TimeoutError:
          pass
