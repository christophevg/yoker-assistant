"""Smoke test for the mailbox seam (P1-003).

Full seam behavior tests (DI stubs, html_body routing assertions, etc.) land
in P3-003. This test only verifies the seam is importable and constructible
with a dummy ``EmailAccount`` — no network.
"""

from simple_email_gw import EmailAccount

from yoker_assistant.mailbox import Mailbox


def test_mailbox_constructs_without_network() -> None:
  """Mailbox builds from a dummy EmailAccount with no connection attempted."""
  account = EmailAccount(
    name="test",
    imap_host="imap.example.com",
    smtp_host="smtp.example.com",
    username="assistant@example.com",
    password="dummy",
  )
  mailbox = Mailbox(account)
  assert mailbox is not None
  for method in ("connect", "close", "unread_ids", "fetch", "reply", "mark_read", "archive"):
    assert hasattr(mailbox, method), f"Mailbox missing {method}"


class _RecordingSMTP:
  """Stub SMTP client: records kwargs of reply_email / send_email calls."""

  def __init__(self) -> None:
    self.calls: list[tuple[str, dict]] = []

  async def reply_email(self, to, subject, body, html_body=None, in_reply_to=None, **kwargs):
    self.calls.append(
      (
        "reply_email",
        {
          "to": to,
          "subject": subject,
          "body": body,
          "html_body": html_body,
          "in_reply_to": in_reply_to,
        },
      )
    )
    return {"status": "sent"}

  async def send_email(self, to, subject, body, html_body=None, **kwargs):
    self.calls.append(
      ("send_email", {"to": to, "subject": subject, "body": body, "html_body": html_body})
    )
    return {"status": "sent"}


async def test_reply_routes_html_through_html_body_kwarg() -> None:
  """reply() routes HTML via html_body= and text via body=, branching on in_reply_to."""
  account = EmailAccount(
    name="test",
    imap_host="imap.example.com",
    smtp_host="smtp.example.com",
    username="assistant@example.com",
    password="dummy",
  )
  mailbox = Mailbox(account)
  stub = _RecordingSMTP()
  mailbox._smtp = stub

  await mailbox.reply(
    "owner@example.com", "Re: test", "<p>hi</p>", in_reply_to="<msg-id@example.com>"
  )
  await mailbox.reply("owner@example.com", "Re: test", "<p>hi</p>", in_reply_to=None)

  assert stub.calls[0][0] == "reply_email"
  assert stub.calls[0][1]["html_body"] == "<p>hi</p>"
  assert stub.calls[0][1]["body"] == ""
  assert stub.calls[0][1]["in_reply_to"] == "<msg-id@example.com>"
  assert stub.calls[1][0] == "send_email"
  assert stub.calls[1][1]["html_body"] == "<p>hi</p>"
  assert stub.calls[1][1]["body"] == ""
