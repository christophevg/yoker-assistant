"""Unit tests for :mod:`yoker_assistant.loop`.

Covers ``build_message`` (the P2-006 handoff payload function), the
``_contains_unsafe_html`` guardrail, the four-way branching in
``_process_one``, and the C1 startup whitelist guard in ``run``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from yoker_assistant.loop import (
  NO_REPLY_SENTINEL,
  _contains_unsafe_html,
  _process_one,
  build_message,
  run,
)

# ---------------------------------------------------------------------------
# build_message
# ---------------------------------------------------------------------------


def test_build_message_formats_headers_and_body() -> None:
  """build_message produces From/Subject/Date headers + blank line + body."""
  msg = {
    "from": "alice@example.com",
    "subject": "Hello",
    "date": "Mon, 1 Jan 2026 00:00:00 +0000",
    "body": "Hi there.",
  }
  assert build_message(msg) == (
    "From: alice@example.com\nSubject: Hello\nDate: Mon, 1 Jan 2026 00:00:00 +0000\n\nHi there."
  )


def test_build_message_collapses_crlf_in_headers() -> None:
  """CR/LF in header values is replaced with spaces to prevent injection."""
  msg = {
    "from": "alice\r\nBcc: evil@example.com\r\n",
    "subject": "Hi\n\r\nInjected-Header: x",
    "date": "Mon\r\n1 Jan",
    "body": "body",
  }
  out = build_message(msg)
  # No raw CR/LF inside the header section (the first 3 lines + blank line).
  header_block = out.split("\n\n", 1)[0]
  assert "\r" not in header_block
  # The injected Bcc text survives as a flattened space-separated string,
  # not as a real header line.
  assert "Bcc: evil@example.com" not in out.split("\n")


def test_build_message_missing_fields_become_empty_strings() -> None:
  """Missing fields are substituted with empty strings, not crashes."""
  out = build_message({})
  assert out == "From: \nSubject: \nDate: \n\n"


def test_build_message_preserves_body_verbatim() -> None:
  """Body is passed through unchanged, including newlines."""
  msg = {"body": "line1\nline2\r\nline3"}
  assert build_message(msg).endswith("line1\nline2\r\nline3")


# ---------------------------------------------------------------------------
# _contains_unsafe_html
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
  "html",
  [
    "<script>alert(1)</script>",
    "<STYLE>body{}</STYLE>",
    "<img src=x onerror=alert(1)>",
    "<iframe src=evil></iframe>",
    "<object data=evil></object>",
    "<embed src=evil>",
    "<form action=evil></form>",
    '<div onclick="alert(1)">x</div>',
    '<div onload="alert(1)">x</div>',
    "<p onmouseover=alert(1)>x</p>",
  ],
)
def test_contains_unsafe_html_detects_unsafe(html: str) -> None:
  """Unsafe tags and on* event handlers are flagged."""
  assert _contains_unsafe_html(html) is True


@pytest.mark.parametrize(
  "html",
  [
    "<p>hello</p>",
    "<strong>bold</strong>",
    "<ul><li>item</li></ul>",
    "<h1>Title</h1>",
    "<table><tr><td>cell</td></tr></table>",
    "plain text, no html at all",
  ],
)
def test_contains_unsafe_html_passes_clean(html: str) -> None:
  """Clean HTML and plain text pass the guard."""
  assert _contains_unsafe_html(html) is False


# ---------------------------------------------------------------------------
# _process_one four-way branching
# ---------------------------------------------------------------------------


def _make_msg(from_: str = "Owner <owner@example.com>", subject: str = "Hi") -> dict[str, Any]:
  """Return a fetch_message-shaped dict matching simple_email_gw's contract."""
  return {
    "id": "1",
    "folder": "INBOX",
    "subject": subject,
    "from": from_,
    "to": "assistant@example.com",
    "date": "Mon, 1 Jan 2026 00:00:00 +0000",
    "body": "message body",
    "attachments": [],
    "read": False,
    "message_id": "<orig@example.com>",
    "references": [],
  }


def _make_clients(reply_html: str) -> tuple[MagicMock, MagicMock, MagicMock]:
  """Build mocked imap/smtp/agent with the agent returning ``reply_html``."""
  imap = MagicMock()
  imap.fetch_message = AsyncMock(return_value=_make_msg())
  imap.mark_message = AsyncMock(return_value=True)
  imap.move_message = AsyncMock(return_value=True)
  smtp = MagicMock()
  smtp.reply_email = AsyncMock(return_value={"status": "sent"})
  agent = MagicMock()
  agent.process = AsyncMock(return_value=reply_html)
  return imap, smtp, agent


async def test_process_one_sentinel_marks_and_archives_no_reply() -> None:
  """Branch 1: {{NO_REPLY}} → mark read + archive, no reply_email call."""
  imap, smtp, agent = _make_clients(NO_REPLY_SENTINEL)
  await _process_one(imap, smtp, agent, "1")
  imap.mark_message.assert_awaited_once_with("1", "INBOX", "\\Seen", action="add")
  imap.move_message.assert_awaited_once_with("1", "INBOX", "Archive")
  smtp.reply_email.assert_not_awaited()


async def test_process_one_sentinel_wrapped_in_html_still_detected() -> None:
  """The sentinel inside HTML is still detected (substring match)."""
  imap, smtp, agent = _make_clients(f"<p>{NO_REPLY_SENTINEL}</p>")
  await _process_one(imap, smtp, agent, "1")
  imap.mark_message.assert_awaited_once()
  imap.move_message.assert_awaited_once()
  smtp.reply_email.assert_not_awaited()


async def test_process_one_empty_reply_leaves_unseen() -> None:
  """Branch 2: empty/whitespace reply → no mark, no archive, no send."""
  imap, smtp, agent = _make_clients("   \n  \t ")
  await _process_one(imap, smtp, agent, "1")
  imap.mark_message.assert_not_awaited()
  imap.move_message.assert_not_awaited()
  smtp.reply_email.assert_not_awaited()


async def test_process_one_guard_failure_marks_no_archive_sends_notice() -> None:
  """Branch 3: unsafe HTML → mark read (no archive) + plain-text notice to sender."""
  imap, smtp, agent = _make_clients("<script>alert(1)</script>")
  await _process_one(imap, smtp, agent, "1")
  imap.mark_message.assert_awaited_once_with("1", "INBOX", "\\Seen", action="add")
  imap.move_message.assert_not_awaited()
  smtp.reply_email.assert_awaited_once()
  call = smtp.reply_email.call_args
  assert call.kwargs["to"] == "owner@example.com"
  assert call.kwargs["subject"] == "Re: Hi"
  assert "unable to produce a safe reply" in call.kwargs["body"]
  assert call.kwargs["in_reply_to"] == "<orig@example.com>"
  assert "html_body" not in call.kwargs


async def test_process_one_valid_reply_sends_html_then_marks_and_archives() -> None:
  """Branch 4: valid HTML → reply_email with html_body + mark read + archive."""
  imap, smtp, agent = _make_clients("<p>Hello.</p>")
  await _process_one(imap, smtp, agent, "1")
  smtp.reply_email.assert_awaited_once()
  call = smtp.reply_email.call_args
  assert call.kwargs["to"] == "owner@example.com"
  assert call.kwargs["subject"] == "Re: Hi"
  assert call.kwargs["body"] == ""
  assert call.kwargs["html_body"] == "<p>Hello.</p>"
  assert call.kwargs["in_reply_to"] == "<orig@example.com>"
  imap.mark_message.assert_awaited_once_with("1", "INBOX", "\\Seen", action="add")
  imap.move_message.assert_awaited_once_with("1", "INBOX", "Archive")


# ---------------------------------------------------------------------------
# run() C1 startup guard
# ---------------------------------------------------------------------------


async def test_run_refuses_to_start_when_whitelist_disabled(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """run() raises RuntimeError when the recipient whitelist is disabled."""
  whitelist = MagicMock()
  whitelist.enabled = False
  monkeypatch.setattr("yoker_assistant.loop.get_recipient_whitelist", lambda: whitelist)
  with pytest.raises(RuntimeError, match="recipient whitelist"):
    await run(once=True)


def _enable_whitelist(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
  """Patch get_recipient_whitelist to return an enabled whitelist."""
  whitelist = MagicMock()
  whitelist.enabled = True
  monkeypatch.setattr("yoker_assistant.loop.get_recipient_whitelist", lambda: whitelist)
  return whitelist


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
  """Set the EMAIL_* env vars _account_from_env reads."""
  for key, value in {
    "EMAIL_NAME": "test",
    "EMAIL_IMAP_HOST": "imap.example.com",
    "EMAIL_SMTP_HOST": "smtp.example.com",
    "EMAIL_USERNAME": "user",
    "EMAIL_PASSWORD": "pass",
  }.items():
    monkeypatch.setenv(key, value)


async def test_run_proceeds_when_whitelist_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
  """C1 happy path: run() does not raise when whitelist is enabled."""
  _enable_whitelist(monkeypatch)
  _set_env(monkeypatch)

  imap = MagicMock()
  imap.connect = AsyncMock()
  imap.search = AsyncMock(return_value=[])
  imap.disconnect = AsyncMock()
  monkeypatch.setattr("yoker_assistant.loop.IMAPClient", lambda account: imap)

  smtp = MagicMock()
  monkeypatch.setattr("yoker_assistant.loop.SMTPClient", lambda account: smtp)

  agent = MagicMock()
  agent.process = AsyncMock(return_value=NO_REPLY_SENTINEL)
  monkeypatch.setattr("yoker_assistant.loop.Agent", lambda **kwargs: agent)

  # Should not raise — proceeds to connect + search, then breaks (once + empty).
  await run(once=True)

  imap.connect.assert_awaited_once()
  imap.search.assert_awaited_with("INBOX", "UNSEEN")
  imap.disconnect.assert_awaited_once()


async def test_run_continues_after_process_one_exception(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  """§7 robustness: if _process_one raises, the loop continues to the next message."""
  _enable_whitelist(monkeypatch)
  _set_env(monkeypatch)

  imap = MagicMock()
  imap.connect = AsyncMock()
  imap.search = AsyncMock(return_value=["msg1", "msg2"])
  imap.fetch_message = AsyncMock(return_value=_make_msg())
  imap.disconnect = AsyncMock()
  monkeypatch.setattr("yoker_assistant.loop.IMAPClient", lambda account: imap)

  smtp = MagicMock()
  smtp.reply_email = AsyncMock(return_value={"status": "sent"})
  monkeypatch.setattr("yoker_assistant.loop.SMTPClient", lambda account: smtp)

  agent = MagicMock()
  # First process call is the Initialize setup turn; then per-message calls:
  # first raises, second succeeds.
  agent.process = AsyncMock(side_effect=[NO_REPLY_SENTINEL, Exception("boom"), "<p>ok</p>"])
  monkeypatch.setattr("yoker_assistant.loop.Agent", lambda **kwargs: agent)

  # Should not propagate — the per-message exception is caught and logged.
  await run(once=True)

  # The loop continued past msg1's failure to process msg2.
  assert agent.process.await_count == 3  # Initialize + 2 messages
  assert imap.fetch_message.await_count == 2
  imap.disconnect.assert_awaited_once()
