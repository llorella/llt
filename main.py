#!/usr/bin/env python3
"""Compatibility entry point for source checkouts.

The packaged CLI lives at ``llt.cli.__main__``. This wrapper keeps old symlink
installs working while the project moves to normal Python packaging.
"""

from __future__ import annotations

import os
import sys


def _ensure_src_on_path() -> None:
    repo_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)


def main() -> None:
    _ensure_src_on_path()
    from llt.cli.__main__ import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
