from pathlib import Path

import pytest

from anchor import config

EXAMPLE = Path(__file__).resolve().parent.parent / "anchor.example.toml"


def test_no_file_means_open_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("ANCHOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = config.load()
    assert cfg["default_role"] == "pwdr"
    assert cfg["people"] == {} and cfg["smes"] == []
    assert cfg["promote"]["enforce"] == "signal"
    assert list(cfg["roles"]) == ["researcher", "pwdr", "stakeholder"]


def test_example_file_loads_and_matches_defaults():
    cfg = config.load(EXAMPLE)
    for key in ("modes", "levels", "checks", "moments", "outcome_after_days", "default_role"):
        assert cfg[key] == config.DEFAULTS[key], key
    assert set(cfg["roles"]) == set(config.DEFAULTS["roles"])


def test_team_can_rename_and_add_without_code(tmp_path, monkeypatch):
    path = tmp_path / "anchor.toml"
    path.write_text('''
default_role = "stakeholder"
smes = ["Sam"]
moments = ["used"]
[roles.data_science]
label = "Data science"
[people]
"Sam" = "data_science"
[levels]
insight = "Big idea"
[[study.fields]]
key = "intake_link"
''')
    monkeypatch.setenv("ANCHOR_CONFIG", str(path))
    cfg = config.load()
    assert cfg["levels"]["insight"] == "Big idea"
    assert cfg["levels"]["finding"] == "Finding"  # untouched defaults stay
    assert cfg["roles"]["data_science"] == {"label": "Data science"}
    assert cfg["study"]["fields"][0] == {"key": "intake_link", "label": "Intake link", "required": False,
                                         "ask_at": "running"}


@pytest.mark.parametrize("bad", [
    {"default_role": "nobody"},
    {"people": {"Sam": "wizard"}},
    {"smes": "Sam"},
    {"promote": {"enforce": "sometimes"}},
    {"modes": ["home", "dashboard"]},
    {"moments": ["fireworks"]},
    {"study": {"fields": [{"label": "no key"}]}},
    {"study": {"fields": [{"key": "x", "ask_at": "someday"}]}},
])
def test_bad_config_is_explained(bad):
    with pytest.raises(config.ConfigError):
        config.from_dict(bad)


def test_config_is_served_to_the_app(store):
    from anchor.api import handle
    status, data = handle(store, "GET", "/api/config")
    assert status == 200 and data["levels"]["insight"] == "Insight"
    assert "people" not in data and "smes" not in data


def test_moments_can_be_turned_off(make_store):
    store = make_store({"moments": []})
    lid = store.add("x is 1", "observation", "Jo")["learning"]["id"]
    store.promote(lid, "Kim")
    assert store.next_step("Jo")["moment"] is None
