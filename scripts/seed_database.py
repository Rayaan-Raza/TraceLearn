"""CLI entrypoint to initialize and seed the TraceLearn database."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.seed import SEED_EXPECTED_COUNTS, seed_database


def main() -> None:
    seed_database()
    print("Seed complete:", SEED_EXPECTED_COUNTS)


if __name__ == "__main__":
    main()
