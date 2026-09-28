"""Team config: how a team makes ANCHOR fit the way it already works.

Everything here is optional. With no config file, ANCHOR runs fully open:
anyone can do anything, new names get the default role, and nothing is
required beyond what a finding needs to exist.

The file is plain TOML. Its path comes from ANCHOR_CONFIG, or anchor.toml in
the current folder if that exists. See anchor.example.toml for every option.
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
    # Role keys are stable ids. Labels are what people see. A trusted role's
    # validations count as trusted in the summary; everyone else's count as peer.
    # Roles never block an action unless a team turns on a rule that says so.
    "roles": {
        "researcher": {"label": "Researcher", "trusted": True},
        "trusted_reviewer": {"label": "Trusted reviewer", "trusted": True},
        "contributor": {"label": "People who do research", "trusted": False},
        "stakeholder": {"label": "Stakeholder", "trusted": False},
    },
    # Role given to a name the first time it is seen.
    "default_role": "contributor",
    # name = role key. The file is the source of truth for anyone listed here.
    "people": {},
    "tiers": {"data_point": "Data point", "hypothesis": "Hypothesis", "insight": "Insight"},
    # How a validator checked a finding. Shown next to their validation.
    "checks": {
        "evidence": "Reviewed the evidence",
        "source_data": "Checked the source data",
        "reproduced": "Reproduced it",
        "judgment": "Domain judgment",
    },
    "study": {
        # Extra fields every study captures, on top of objective, decision,
        # method, and sample. Each is {key, label, help, required}. Required
        # fields warn when empty; they never block.
        "fields": [],
    },
    "promote": {
        # A finding is "ready to promote" when any rule set here is met. With no
        # rules, every finding is ready. Readiness is a signal unless
        # enforce = "required", which stops promotion until a rule is met.
        "min_validations": 0,
        "min_trusted_validations": 0,
        "trusted_roles_ready": False,
        "enforce": "signal",
    },
    # Which work modes the app shows in its navigation.
    "modes": ["home", "studies", "findings", "explore", "validate", "decisions"],
}

MODES = ("home", "studies", "findings", "explore", "validate", "decisions")


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
        role["trusted"] = bool(role.get("trusted", False))
    if cfg["default_role"] not in roles:
        raise ConfigError(f"default_role '{cfg['default_role']}' is not one of the roles")
    for name, role in cfg["people"].items():
        if role not in roles:
            raise ConfigError(f"[people] {name} has role '{role}', which is not one of the roles")
    for field in cfg["study"]["fields"]:
        if "key" not in field:
            raise ConfigError("each [[study.fields]] needs a key")
        field.setdefault("label", field["key"].replace("_", " ").capitalize())
        field["required"] = bool(field.get("required", False))
    if cfg["promote"]["enforce"] not in ("signal", "required"):
        raise ConfigError("[promote] enforce must be 'signal' or 'required'")
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
    return {k: cfg[k] for k in ("roles", "default_role", "tiers", "checks", "study", "promote", "modes")}
