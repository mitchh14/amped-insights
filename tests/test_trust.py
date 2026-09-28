from anchor.api import handle


def test_trust_summary_by_role_and_how_checked(make_store):
    store = make_store({"people": {"Sam": "researcher", "Lee": "researcher", "Dana": "trusted_reviewer"}})
    fid = store.propose("Long address forms drive mobile abandonment", "hypothesis", "Jo")["finding"]["id"]
    assert store.get(fid)["trust"]["summary"] == "Not validated yet."

    store.validate(fid, "Kim", "Looks right to me")
    store.validate(fid, "Sam", basis="source_data")
    store.validate(fid, "Lee", basis="reproduced")
    store.validate(fid, "Dana", "Scope it to mobile web", outcome="changes_requested")
    f = store.get(fid)
    assert f["trust"]["by_role"] == {"peer": 1, "researcher": 2}
    assert (f["trust"]["trusted"], f["trust"]["peer"], f["trust"]["changes_requested"]) == (2, 1, 1)
    assert f["trust"]["summary"] == (
        "Validated by 2 researcher, 1 peer. "
        "How they checked: checked the source data (1), reproduced it (1). "
        "1 asks for changes."
    )
    # Trusted reviews are listed first, each with its role.
    assert [(v["validated_by"], v["role_label"]) for v in f["validations"]] == [
        ("Sam", "Researcher"), ("Lee", "Researcher"), ("Dana", "Trusted reviewer"),
        ("Kim", "People who do research"),
    ]


def test_role_is_recorded_as_it_was_at_review_time(make_store):
    store = make_store()
    fid = store.propose("x is 1", "data_point", "Jo")["finding"]["id"]
    store.validate(fid, "Sam")
    store.set_role("Sam", "researcher", by="Lee")
    v = store.get(fid)["validations"][0]
    assert v["role"] == "contributor" and v["trusted"] is False
    assert store.get(fid)["trust"]["summary"] == "Validated by 1 peer."


def test_custom_trusted_role_counts_as_trusted(make_store):
    store = make_store({"roles": {"data_science": {"label": "Data science", "trusted": True}},
                        "people": {"Ren": "data_science"}})
    fid = store.propose("Conversion is 42 percent", "data_point", "Jo")["finding"]["id"]
    store.validate(fid, "Ren", basis="source_data")
    assert store.get(fid)["trust"]["summary"].startswith("Validated by 1 data science.")


def test_trust_is_in_query_results(store):
    fid = store.propose("Mobile checkout conversion is 42 percent", "data_point", "Jo")["finding"]["id"]
    store.validate(fid, "Sam")
    hit = handle(store, "GET", "/api/findings?q=checkout")[1][0]
    assert hit["trust"]["summary"] == "Validated by 1 peer."
