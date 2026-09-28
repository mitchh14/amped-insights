import pytest

from anchor.core import CoreError


def test_names_match_without_case_and_join_on_first_use(store):
    lid = store.add("Conversion is 42 percent", "observation", "Ana")["learning"]["id"]
    assert store.get(lid)["owner"] == "Ana"
    with pytest.raises(CoreError):
        store.review(lid, "ana")  # the same person as "Ana"
    store.review(lid, "sam")
    assert [p["name"] for p in store.people()] == ["Ana", "sam"]
    assert all(p["role"] == "pwdr" and p["sme"] is False for p in store.people())
    assert [e["kind"] for e in store.activity()].count("joined") == 2


def test_roles_and_smes_come_from_config(make_store):
    store = make_store({"people": {"Sam": "researcher"}, "smes": ["Dana"]})
    assert store.whoami("sam") == {"name": "Sam", "role": "researcher", "role_label": "Researcher", "sme": False}
    assert store.whoami("dana") == {"name": "Dana", "role": "pwdr", "role_label": "PwDR", "sme": True}
    lid = store.add("Conversion is 42 percent", "observation", "Ana")["learning"]["id"]
    r = store.review(lid, "DANA")["learning"]["reviews"][0]
    assert (r["by"], r["role"], r["sme"]) == ("Dana", "pwdr", True)


def test_config_is_source_of_truth_on_restart(make_store):
    store = make_store({"people": {"Sam": "researcher"}, "smes": ["Sam"]})
    r = store.set_person("Sam", "Lee", role="stakeholder", sme=False)
    assert r["warnings"]  # the config will put it back
    assert store.whoami("Sam")["role"] == "stakeholder"
    again = make_store({"people": {"Sam": "researcher"}, "smes": ["Sam"]})
    assert again.whoami("Sam") == {"name": "Sam", "role": "researcher", "role_label": "Researcher", "sme": True}


def test_set_person_is_logged_and_checked(store):
    store.set_person("Dana", "Sam", sme=True)
    assert store.whoami("dana")["sme"] is True
    event = store.activity()[0]
    assert event["kind"] == "person_set" and event["text"] == "Sam set Dana: SME"
    with pytest.raises(CoreError):
        store.set_person("Dana", "Sam", role="boss")
    with pytest.raises(CoreError):
        store.set_person("Dana", "Sam")


def test_custom_default_role(make_store):
    assert make_store({"default_role": "stakeholder"}).whoami("Morgan")["role"] == "stakeholder"
