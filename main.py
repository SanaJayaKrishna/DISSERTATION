"""Repository-level wrapper for the capability extractor CLI."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(repo_dir))
    from capability_extractor.main import main as package_main

    return package_main()


if __name__ == "__main__":
    raise SystemExit(main())
