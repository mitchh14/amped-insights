from pathlib import Path

import pytest

from anchor import config

EXAMPLE = Path(__file__).resolve().parent.parent / "anchor.example.toml"


def test_no_file_means_open_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("ANCHOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = config.load()
    assert cfg["default_role"] == "contributor"
    assert cfg["people"] == {}
    assert cfg["promote"]["enforce"] == "signal"
    assert cfg["roles"]["researcher"]["trusted"] is True


def test_example_file_loads_and_matches_defaults():
    cfg = config.load(EXAMPLE)
    assert cfg["modes"] == config.DEFAULTS["modes"]
    assert set(cfg["roles"]) == set(config.DEFAULTS["roles"])
    assert cfg["tiers"] == config.DEFAULTS["tiers"]


def test_team_can_rename_and_add_without_code(tmp_path, monkeypatch):
    path = tmp_path / "anchor.toml"
    path.write_text('''
default_role = "stakeholder"
[roles.data_science]
label = "Data science"
trusted = true
[people]
"Sam" = "data_science"
[tiers]
insight = "Learning"
[[study.fields]]
key = "intake_link"
''')
    monkeypatch.setenv("ANCHOR_CONFIG", str(path))
    cfg = config.load()
    assert cfg["tiers"]["insight"] == "Learning"
    assert cfg["tiers"]["hypothesis"] == "Hypothesis"  # untouched defaults stay
    assert cfg["roles"]["data_science"] == {"label": "Data science", "trusted": True}
    assert cfg["study"]["fields"][0] == {"key": "intake_link", "label": "Intake link", "required": False}


@pytest.mark.parametrize("bad", [
    {"default_role": "nobody"},
    {"people": {"Sam": "wizard"}},
    {"promote": {"enforce": "sometimes"}},
    {"modes": ["home", "dashboard"]},
    {"study": {"fields": [{"label": "no key"}]}},
])
def test_bad_config_is_explained(bad):
    with pytest.raises(config.ConfigError):
        config.from_dict(bad)


def test_config_is_served_to_the_app(store):
    from anchor.api import handle
    status, data = handle(store, "GET", "/api/config")
    assert status == 200 and data["tiers"]["insight"] == "Insight"
    assert "people" not in data
