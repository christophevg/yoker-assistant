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
from yoker.ui import UIBridge

from yoker_assistant import __version__
from yoker_assistant.handler import RichUIHandler

# suppress audit logging from simple_email_gw
logger = logging.getLogger("simple_email_gw.audit")
logger.setLevel(logging.WARNING)

NO_REPLY_SENTINEL = "{{NO_REPLY}}"
_INITIALIZE_PROMPT = "Initialize and reply only with OK when ready."
_POLL_INTERVAL = 60  # seconds between polls when inbox is empty
_INBOX_FOLDER = "INBOX"
_ARCHIVE_FOLDER = "Archive"
_ACCOUNT_NAME = "default"  # we use the default (convention) simple email gw account

_UNSAFE_TAGS = ("<script", "<style", "<img", "<iframe", "<object", "<embed", "<form")
_UNSAFE_HANDLER = re.compile(r"\son\w+\s*=")

# we use the Rich UI Handler for all output
ui = RichUIHandler()


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
      """Recipient whitelist is disabled — refusing to run (fails open).
Set EMAIL_RECIPIENT_DOMAINS, EMAIL_RECIPIENT_ADDRESSES,
or EMAIL_RECIPIENT_WHITELIST_JSON to enable outgoing reply safety."""
    )

  config = get_yoker_config()
  config.agent = "yoker_assistant:assistant"

  # Inject plugin configuration so the user does not need a yoker.toml just
  # for plugin registration.  This is the programmatic equivalent of the
  # --plugins-enabled CLI flag used by yoker-writing-assistant.  pkgq is also
  # injected because the agent definition uses pkgq:find.  The user confirms
  # trust interactively on first run via yoker's standard trust prompt.
  config.plugins.enabled = True
  for pkg in ("yoker_assistant", "pkgq"):
    if pkg not in config.plugins.packages:
      config.plugins.packages = (*config.plugins.packages, pkg)

  # setup mail servers
  pool = await get_pool()
  imap = await pool.get_imap_client(_ACCOUNT_NAME)
  smtp = await pool.get_smtp_client(_ACCOUNT_NAME)

  # setup signal handling for termination
  stop = asyncio.Event()
  loop = asyncio.get_running_loop()
  for sig in (SIGINT, SIGTERM):
    try:
      loop.add_signal_handler(sig, stop.set)
    except NotImplementedError:
      # Windows — signal handlers not supported on this event loop.
      pass

  async with Session(
    config, session_id="personal", console_logging=False, on_event=UIBridge(ui)
  ) as session:
    await ui.start(session.agent, title="YokerAssistant", version=__version__)

    # one-time session-setup turn
    ui.output_prompt(_INITIALIZE_PROMPT)
    _ = await session.agent.process(_INITIALIZE_PROMPT)

    while not stop.is_set():
      _ = await imap.connect()
      try:
        with ui.console.status("checking email", spinner="star"):
          uids = await imap.search(_INBOX_FOLDER, "UNSEEN")
        if uids:
          ui.output_info(f"📨 {len(uids)} new mail{'s' if len(uids) > 1 else ''}")
          for mid in uids:
            if stop.is_set():  # if interrupted during previous uid handling
              break
            try:
              await _process_one(imap, smtp, session.agent, mid)
            except Exception as ex:
              # per-message exceptions are logged and skipped. The message
              # stays UNSEEN → retried next iteration.
              ui.output_error(ex)
              continue
      finally:
        try:
          await imap.disconnect()
        except Exception as ex:
          ui.output_error(ex)

      if once:
        break

      if not uids:
        try:
          with ui.console.status("", spinner="clock"):
            _ = await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL)
        except asyncio.TimeoutError:
          pass


async def _process_one(
  imap: IMAPClient,
  smtp: SMTPClient,
  agent: Agent,
  message_id: str,
) -> None:
  """Process a single incoming message through the four-way branching."""
  msg = await imap.fetch_message(message_id, _INBOX_FOLDER)
  handoff = build_message(msg)

  ui.output_prompt(handoff)
  reply_html = await agent.process(handoff)

  sender = parseaddr(msg.get("from", ""))[1]
  subject = msg.get("subject", "")
  in_reply_to = msg.get("message_id", "")

  if NO_REPLY_SENTINEL in reply_html:
    # Branch 1: intentional no-reply → mark read + archive.
    _ = await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    _ = await imap.move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)
  elif not reply_html.strip():
    # Branch 2: empty/whitespace → transient problem → leave UNSEEN for retry.
    ui.output_info(f"⚠️ agent returned empty reply: message_id={message_id}")
  elif _contains_unsafe_html(reply_html):
    # Branch 3: guard failure → mark read (no archive) + reply notice to sender.
    _ = await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    notice = (
      "The assistant was unable to produce a safe reply to your message. "
      "Your message was received but no reply will be sent. "
      "If you believe this is an error, please try again later."
    )
    _ = await smtp.reply_email(
      to=sender, subject=f"Re: {subject}", body=notice, in_reply_to=in_reply_to, append_to_sent=True
    )
    ui.output_info("📤 reply sent")
  else:
    # Branch 4: valid reply → send + mark read + archive.
    _ = await smtp.reply_email(
      to=sender,
      subject=f"Re: {subject}",
      body="",
      html_body=reply_html,
      in_reply_to=in_reply_to,
      append_to_sent=True,
    )
    ui.output_info("📤 reply sent")
    _ = await imap.mark_message(message_id, _INBOX_FOLDER, "\\Seen", action="add")
    _ = await imap.move_message(message_id, _INBOX_FOLDER, _ARCHIVE_FOLDER)


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
