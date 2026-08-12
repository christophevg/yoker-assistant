"""Entry point for ``python -m yoker_assistant``.

Thin CLI wrapper around :func:`yoker_assistant.loop.run`.

Pre-flight bootstrap: before starting the email loop, we check
``config_provided()``. When no yoker configuration is found, the
interactive bootstrap wizard runs so the user can create one. After the
wizard writes ``~/.yoker.toml`` the user must manually edit it to set
``enabled = true`` — completing the wizard does not enable Yoker.
"""

import argparse
import asyncio
import logging
import sys

from yoker.bootstrap import BootstrapResult, BootstrapWizard, config_provided
from yoker.bootstrap.steps import DOCS_HOME_URL
from yoker.ui import InteractiveUIHandler

from yoker_assistant.loop import run

# configure logging
logger = logging.getLogger("yoker-assistant")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("logging ready...")


def _run_bootstrap_wizard() -> None:
  """Run the first-run bootstrap wizard when no config is found.

  Interactive (TTY): runs ``BootstrapWizard`` so the user can configure a
  provider and model. The wizard writes ``~/.yoker.toml`` with ``enabled =
  false`` (Config defaults) — the user must then manually set ``enabled =
  true`` and re-run.

  Non-interactive (no TTY): aborts with a message pointing to the docs.
  """
  if not sys.stdin.isatty():
    sys.stderr.write(
      f"No yoker configuration found at ~/.yoker.toml or ./yoker.toml.\n"
      f"Run `yoker-assistant` interactively to configure, "
      f"or see {DOCS_HOME_URL}\n"
      "Aborting (non-interactive mode).\n"
    )
    sys.exit(1)

  # history_file="none" prevents bootstrap prompts (including API keys) from
  # being persisted to ~/.yoker_history.
  ui = InteractiveUIHandler(history_file="none", show_prompts=False)
  try:
    result = asyncio.run(BootstrapWizard(ui).run())
  except KeyboardInterrupt:
    sys.stderr.write("Aborted. No configuration written.\n")
    sys.exit(0)

  if result == BootstrapResult.WRITTEN:
    sys.stdout.write(
      "\nConfiguration written to ~/.yoker.toml.\n"
      "Edit it and set `enabled = true` to acknowledge the risks of running\n"
      "an LLM-powered agent, then re-run `yoker-assistant`.\n"
    )
    sys.exit(0)

  # MANUAL or ABORTED: the wizard already emitted its message.
  sys.exit(0)


def main() -> None:
  """Run the assistant email loop.

  Pass ``--once`` to process a single poll iteration and exit (useful for
  tests and demos).
  """
  # Pre-flight: detect missing configuration before starting the loop.
  if not config_provided():
    _run_bootstrap_wizard()

  parser = argparse.ArgumentParser(prog="yoker-assistant", description="yoker-assistant email loop")
  parser.add_argument("--once", action="store_true", help="process one poll iteration and exit")
  args = parser.parse_args()
  try:
    asyncio.run(run(once=args.once))
  except KeyboardInterrupt:
    sys.exit(0)


if __name__ == "__main__":
  main()
