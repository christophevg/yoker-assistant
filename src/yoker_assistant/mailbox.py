"""Thin async seam over ``simple_email_gw``'s IMAP/SMTP clients.

Each method delegates to exactly one ``simple_email_gw`` call; ``reply()``
branches between ``reply_email`` and ``send_email`` on whether
``in_reply_to`` is given. No business logic, no recipient allowlist (that
lives in the gateway), no HTML re-rendering, no exception wrapping — the
loop (P2-005) owns backoff/skip and the startup whitelist-enabled check.
HTML replies route through the gateway's ``html_body=`` kwarg so they are
sent as ``text/html`` (blocking security requirement).
"""

from typing import Any

from simple_email_gw import EmailAccount, IMAPClient, SMTPClient


class Mailbox:
  """One IMAP + one SMTP client over a single ``EmailAccount``."""

  def __init__(
    self,
    account: EmailAccount,
    *,
    inbox_folder: str = "INBOX",
    archive_folder: str = "Archive",
  ) -> None:
    self._inbox_folder = inbox_folder
    self._archive_folder = archive_folder
    self._imap = IMAPClient(account)
    self._smtp = SMTPClient(account)

  async def connect(self) -> None:
    """``await self._imap.connect()``."""
    await self._imap.connect()

  async def close(self) -> None:
    """``await self._imap.disconnect()`` (SMTP is stateless per-send)."""
    await self._imap.disconnect()

  async def unread_ids(self) -> list[str]:
    """``search(folder=self._inbox_folder, criteria="UNSEEN")``."""
    return list(await self._imap.search(folder=self._inbox_folder, criteria="UNSEEN"))

  async def fetch(self, message_id: str) -> dict[str, Any]:
    """``fetch_message(message_id, folder=self._inbox_folder)``.

    Returns the gateway's dict verbatim with keys: ``id``, ``folder``,
    ``subject``, ``from``, ``to``, ``date``, ``body``, ``attachments``,
    ``read``, ``message_id``, ``references``.
    """
    return await self._imap.fetch_message(message_id, folder=self._inbox_folder)  # type: ignore[no-any-return]

  async def reply(
    self,
    to: str,
    subject: str,
    html_body: str,
    in_reply_to: str | None = None,
    *,
    text_body: str = "",
  ) -> None:
    """Send an HTML reply via ``reply_email`` (threaded) or ``send_email``.

    ``html_body`` routes through the gateway's ``html_body=`` kwarg
    (``text/html``); ``text_body`` is the plain-text fallback via ``body=``.
    """
    if in_reply_to is not None:
      await self._smtp.reply_email(
        to=to,
        subject=subject,
        body=text_body,
        html_body=html_body,
        in_reply_to=in_reply_to,
      )
    else:
      await self._smtp.send_email(
        to=[to],
        subject=subject,
        body=text_body,
        html_body=html_body,
      )

  async def mark_read(self, message_id: str) -> bool:
    """``mark_message(..., flag="\\Seen", action="add")``."""
    return bool(await self._imap.mark_message(message_id, self._inbox_folder, "\\Seen", "add"))

  async def archive(self, message_id: str) -> bool:
    """``move_message(..., self._inbox_folder, self._archive_folder)``."""
    return bool(await self._imap.move_message(message_id, self._inbox_folder, self._archive_folder))
