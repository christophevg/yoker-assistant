"""Entry point for ``python -m yoker_assistant``.

P1-001 stub: exits cleanly when no configuration is present. The real loop
lands in P2-005.
"""

import sys


def main() -> None:
  """Run the assistant.

  For now this is a stub: the email gateway (IMAP/SMTP via
  ``simple_email_gw``) is not yet wired in, so it prints a notice and
  exits cleanly.
  """
  print("yoker-assistant: not configured yet (see P2-005).")
  sys.exit(0)


if __name__ == "__main__":
  main()
