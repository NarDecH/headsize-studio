"""``python -m headsize`` launches the GUI."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from headsize.app import run

    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
