"""Load the sample findings into a new database.

Usage: python scripts/seed.py [db_path]   (defaults to ANCHOR_DB or anchor.db)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anchor.core import DEFAULT_DB_PATH, Store  # noqa: E402
from anchor.seed import seed  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
if Path(path).exists():
    sys.exit(f"{path} already exists. Delete it first to reseed.")
seed(Store(path))
print(f"Seeded {path}")
