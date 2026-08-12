"""Entry point for ``python -m yoker_assistant``.

Thin CLI wrapper around :func:`yoker_assistant.loop.run`.
"""

import argparse
import asyncio
import logging
import sys

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


def main() -> None:
  """Run the assistant email loop.

  Pass ``--once`` to process a single poll iteration and exit (useful for
  tests and demos).
  """
  parser = argparse.ArgumentParser(prog="yoker-assistant", description="yoker-assistant email loop")
  parser.add_argument("--once", action="store_true", help="process one poll iteration and exit")
  args = parser.parse_args()
  try:
    asyncio.run(run(once=args.once))
  except KeyboardInterrupt:
    sys.exit(0)


if __name__ == "__main__":
  main()
