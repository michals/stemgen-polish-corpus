"""Package execution entrypoint for `python -m polish_corpus`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
