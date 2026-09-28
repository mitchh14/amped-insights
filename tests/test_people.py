import pytest

from anchor.core import CoreError


def test_names_match_without_case_and_join_on_first_use(store):
    fid = store.propose("Conversion is 42 percent", "data_point", "Ana")["finding"]["id"]
    assert store.get(fid)["owner"] == "Ana"
    # "ana" is the same person as "Ana", so this is a self validation.
    with pytest.raises(CoreError):
        store.validate(fid, "ana")
    store.validate(fid, "sam")
    assert [p["name"] for p in store.people()] == ["Ana", "sam"]
    assert all(p["role"] == "contributor" for p in store.people())
    assert [e["kind"] for e in store.activity()].count("joined") == 2


def test_roles_come_from_config_and_show_next_to_names(make_store):
    store = make_store({"people": {"Sam": "researcher"}})
    assert store.whoami("sam") == {
        "name": "Sam", "role": "researcher", "role_label": "Researcher", "trusted": True,
    }
    fid = store.propose("Conversion is 42 percent", "data_point", "Ana")["finding"]["id"]
    f = store.validate(fid, "SAM")["finding"]
    assert f["owner_role"] == "contributor"
    assert f["validations"][0]["validated_by"] == "Sam"
    assert f["validations"][0]["role"] == "researcher"


def test_config_is_source_of_truth_on_restart(make_store):
    store = make_store({"people": {"Sam": "researcher"}})
    r = store.set_role("Sam", "stakeholder", by="Lee")
    assert r["warnings"]  # the config will put it back
    assert store.whoami("Sam")["role"] == "stakeholder"
    again = make_store({"people": {"Sam": "researcher"}})
    assert again.whoami("Sam")["role"] == "researcher"


def test_set_role_is_logged_and_checked(store):
    store.set_role("Dana", "trusted_reviewer", by="Sam")
    assert store.whoami("dana")["role"] == "trusted_reviewer"
    event = store.activity()[0]
    assert event["kind"] == "role_set"
    assert event["detail"] == {"person": "Dana", "role": "trusted_reviewer", "previous_role": "contributor"}
    with pytest.raises(CoreError):
        store.set_role("Dana", "boss", by="Sam")


def test_custom_default_role(make_store):
    store = make_store({"default_role": "stakeholder"})
    assert store.whoami("Morgan")["role"] == "stakeholder"


def test_older_databases_get_people_backfilled(tmp_path):
    import sqlite3

    from anchor import config
    from anchor.core import Store

    path = str(tmp_path / "old.db")
    Store(path, config.from_dict()).propose("x is 1", "data_point", "Ana")
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM people")
    store = Store(path, config.from_dict({"people": {"ana": "researcher"}}))
    assert store.people()[0]["name"] == "Ana"
    assert store.people()[0]["role"] == "researcher"
