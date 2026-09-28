"""Team config: how a team makes ANCHOR fit the way it already works.

Everything here is optional. With no config file, ANCHOR runs fully open:
anyone can do anything, new names get the default role, and nothing is
required beyond what a learning needs to exist.

The file is plain TOML. Its path comes from ANCHOR_CONFIG, or anchor.toml in
the current folder if that exists. See anchor.example.toml for every option.
The words used here are defined in docs/GLOSSARY.md.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

# The built-in open defaults. A team's file is merged on top of these.
DEFAULTS: dict[str, Any] = {
    # Role keys are stable ids. Labels are what people see. A role says what
    # someone mainly does. It never changes how much their review counts.
    "roles": {
        "researcher": {"label": "Researcher"},
        "pwdr": {"label": "PwDR"},
        "stakeholder": {"label": "Stakeholder"},
    },
    # Role given to a name the first time it is seen.
    "default_role": "pwdr",
    # name = role key. The file is the source of truth for anyone listed here.
    "people": {},
    # People whose reviews count as "Checked by an SME". Anyone can be an SME,
    # whatever their role. The file is the source of truth for anyone listed.
    "smes": [],
    # What the team calls each level. The meaning stays the same.
    "levels": {"observation": "Observation", "finding": "Finding", "insight": "Insight"},
    # How a reviewer checked a learning. Shown next to their review.
    "checks": {
        "evidence": "Read the evidence",
        "source_data": "Checked the source data",
        "reran": "Reran it",
        "judgment": "Expert judgment",
    },
    "study": {
        # Extra fields a study captures. Each is {key, label, help, required,
        # ask_at}. ask_at is the stage the app asks for it: start, running, or
        # finished. Required fields warn at their stage; they never block.
        "fields": [],
    },
    "promote": {
        # A learning is "ready to promote" when any rule set here is met. With
        # no rules, every learning is ready. Readiness is a signal unless
        # enforce = "required", which stops promotion until a rule is met.
        "min_approvals": 0,
        "min_sme_approvals": 0,
        "enforce": "signal",
    },
    # Days after a decision before the app asks what happened.
    "outcome_after_days": 28,
    # Which moments of joy people see. Leave the list empty to turn them off.
    "moments": ["used", "built_on", "checked", "milestone"],
    # Which work modes the app shows in its navigation.
    "modes": ["home", "studies", "learnings", "review", "decisions"],
}

MODES = ("home", "studies", "learnings", "review", "decisions")
MOMENTS = ("used", "built_on", "checked", "milestone")
ASK_AT = ("start", "running", "finished")


class ConfigError(ValueError):
    """Raised when the config file is not valid."""


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _check(cfg: dict) -> dict:
    roles = cfg["roles"]
    for key, role in roles.items():
        if not isinstance(role, dict):
            raise ConfigError(f"[roles.{key}] must be a table with a label")
        role.setdefault("label", key.replace("_", " ").capitalize())
    if cfg["default_role"] not in roles:
        raise ConfigError(f"default_role '{cfg['default_role']}' is not one of the roles")
    for name, role in cfg["people"].items():
        if role not in roles:
            raise ConfigError(f"[people] {name} has role '{role}', which is not one of the roles")
    if not isinstance(cfg["smes"], list) or not all(isinstance(n, str) for n in cfg["smes"]):
        raise ConfigError("smes must be a list of names")
    for field in cfg["study"]["fields"]:
        if "key" not in field:
            raise ConfigError("each [[study.fields]] needs a key")
        field.setdefault("label", field["key"].replace("_", " ").capitalize())
        field["required"] = bool(field.get("required", False))
        field.setdefault("ask_at", "running")
        if field["ask_at"] not in ASK_AT:
            raise ConfigError(f"study field '{field['key']}' ask_at must be one of {ASK_AT}")
    if cfg["promote"]["enforce"] not in ("signal", "required"):
        raise ConfigError("[promote] enforce must be 'signal' or 'required'")
    bad = [m for m in cfg["moments"] if m not in MOMENTS]
    if bad:
        raise ConfigError(f"unknown moments {bad}; choose from {MOMENTS}")
    bad = [m for m in cfg["modes"] if m not in MODES]
    if bad:
        raise ConfigError(f"unknown modes {bad}; choose from {MODES}")
    return cfg


def from_dict(data: dict | None = None) -> dict[str, Any]:
    """Build a full config from a partial dict (as parsed from TOML)."""
    return _check(_merge(DEFAULTS, data or {}))


def load(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Load the team config. Falls back to the open defaults when there is no file."""
    if path is None:
        path = os.environ.get("ANCHOR_CONFIG") or ("anchor.toml" if Path("anchor.toml").exists() else None)
    if path is None:
        return from_dict()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file {path} not found") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None
    return from_dict(data)


def public(cfg: dict) -> dict[str, Any]:
    """The parts of the config the app and AI tools need for display."""
    keys = ("roles", "default_role", "levels", "checks", "study", "promote", "outcome_after_days", "moments", "modes")
    return {k: cfg[k] for k in keys}
