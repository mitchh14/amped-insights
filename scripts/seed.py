"""Load a handful of test findings that exercise the three tiers,
multiple validators, evidence links, a checkout, and a contested pair.

Usage: python scripts/seed.py [db_path]   (defaults to ANCHOR_DB or anchor.db)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anchor.core import DEFAULT_DB_PATH, Store  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
if Path(path).exists():
    sys.exit(f"{path} already exists. Delete it first to reseed.")
s = Store(path)

conv = s.propose("Mobile checkout conversion is 42 percent", "data_point", "Priya (analytics)")["finding"]
s.validate(conv["id"], "Sam (research)", "Matches the Q3 dashboard")
s.validate(conv["id"], "Lee (research)", "Checked against raw event data")

drop = s.propose("Most mobile checkout drop off happens on the address form step", "data_point", "Priya (analytics)")["finding"]
s.validate(drop["id"], "Sam (research)")

quotes = s.propose("6 of 8 interviewed users said typing an address on a phone is tedious", "data_point", "Lee (research)")["finding"]

hyp = s.propose(
    "Users abandon mobile checkout because the address form is too long",
    "hypothesis", "Jordan (PM)", [conv["id"], drop["id"], quotes["id"]],
)["finding"]
s.validate(hyp["id"], "Sam (research)", "Evidence lines up, worth testing autofill")
s.checkout(hyp["id"], "Sam (research)")

ins = s.propose(
    "Address autofill is the highest leverage fix for mobile checkout conversion",
    "insight", "Sam (research)", [hyp["id"]],
)["finding"]

# A new finding that contradicts a validated one.
contra = s.propose(
    "Address form length does not affect mobile checkout abandonment",
    "hypothesis", "Research agent (on behalf of Alex)", [conv["id"]],
)
if contra["possible_conflicts"]:
    other = contra["possible_conflicts"][0]["finding"]["id"]
    s.confirm_conflict(contra["finding"]["id"], other, "Lee (research)",
                       "A/B test from last spring points the other way")

s.propose("Desktop users prefer guest checkout over creating an account", "hypothesis", "Jordan (PM)")

print(f"Seeded {path}")
