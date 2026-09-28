"""The digest, the one next step, follows, change notices, and moments."""


def _kinds(items):
    return [(i["importance"], i["kind"]) for i in items]


def test_digest_leaves_out_noise_and_ranks_what_matters(store):
    lid = store.add("Long forms drive abandonment", "finding", "Jo")["learning"]["id"]
    store.working_on(lid, "Kim")
    store.whoami("Newbie")
    store.review(lid, "Sam")
    store.review(lid, "Dana", "changes", note="Which forms?")
    items = store.digest("Jo")["items"]
    assert _kinds(items) == [(1, "reviewed"), (2, "reviewed")]
    assert items[0]["text"] == 'Dana asked for changes on #1: "Which forms?"'
    assert {i["importance"] for i in store.digest("Sam")["items"]} == {3}  # Sam reviewed it, so hears quietly


def test_you_hear_about_changes_to_what_you_use_or_follow(store):
    lid = store.add("Checkout form is too long for mobile users", "finding", "Jo")["learning"]["id"]
    store.review(lid, "Sam")
    store.log_decision("Shorten the form", "Morgan", [lid])
    store.follow(lid, "Kim")
    assert store.digest("Morgan")["items"] == []  # nothing changed since it was used
    new = store.revise(lid, "Jo", "Checkout form is too long for mobile web users")["learning"]["id"]
    store.promote(new, "Lee")
    for who in ("Morgan", "Kim"):
        texts = [i["text"] for i in store.digest(who)["items"]]
        assert texts == [f'Jo revised #{lid} as #{new}. Was: "Checkout form is too long for mobile users". '
                         f'Now: "Checkout form is too long for mobile web users"']
    store.follow(new, "Kim")
    store.review(new, "Sam")
    assert store.digest("Kim")["items"][0]["text"] == f"#{new} is now Checked by peers"
    store.follow(new, "Kim", on=False)


def test_next_step_order_and_not_now(make_store):
    store = make_store({"smes": ["Sam"], "people": {"Sam": "researcher"}})
    assert store.next_step("Sam")["step"]["kind"] == "suggest"
    store.ask_for_research("Do returning shoppers use saved addresses?", "Morgan")
    assert store.next_step("Sam")["step"]["kind"] == "request"
    lid = store.add("Forms are long", "finding", "Jo")["learning"]["id"]
    store.ask_for_review(lid, "Jo", roles=["sme"])
    n = store.next_step("Sam")
    assert n["step"]["kind"] == "review" and n["later"] == 1
    store.mark_seen("Sam", [n["step"]["key"]])  # "Not now"
    assert store.next_step("Sam")["step"]["kind"] == "request"
    store.add("x is 1", "observation", "Sam", origin="person_with_ai")
    assert store.next_step("Sam")["step"]["kind"] == "confirm"


def test_study_and_outcome_steps(make_store):
    store = make_store({"outcome_after_days": 0})
    sid = store.start_study("Why do shoppers leave?", "Lee", decision="Fund autofill")["study"]["id"]
    store.update_study(sid, "Lee", status="running")
    step = store.next_step("Lee")["step"]
    assert step["kind"] == "study" and "method, who or what we studied" in step["text"]
    store.update_study(sid, "Lee", method="Interviews", sample="8 shoppers")
    store.log_decision("Fund autofill", "Lee")
    assert store.next_step("Lee")["step"]["kind"] == "outcome"


def test_moments_are_shown_once_and_never_compare_people(make_store):
    store = make_store({"smes": ["Dana"]})
    obs = store.add("6 of 8 shoppers find address typing tedious", "observation", "Priya")["learning"]["id"]
    f = store.add("Address forms drive abandonment", "finding", "Jo", [obs])["learning"]["id"]
    m = store.next_step("Priya")["moment"]
    assert m["text"] == f"Jo used your learning #{obs} as evidence."
    store.mark_seen("Priya", [m["key"]])
    assert store.next_step("Priya")["moment"] is None

    store.review(f, "Dana")
    assert store.next_step("Jo")["moment"]["text"] == f"Dana, an SME, approved your learning #{f}."
    ins = store.promote(f, "Lee")["learning"]["id"]
    store.review(ins, "Kim")
    store.log_decision("Fund autofill", "Morgan", [ins])
    texts = [i["text"] for i in store.digest("Priya")["items"] if i["kind"] == "moment"]
    assert 'Morgan used your work in "Fund autofill".' in texts
    lee = [i["text"] for i in store.digest("Lee")["items"] if i["kind"] == "moment"]
    assert f"Your insight #{ins} is now Checked by peers." in lee


def test_milestones_for_you_and_the_team(store):
    for n in range(5):
        lid = store.add(f"Observation number {n}", "observation", "Jo")["learning"]["id"]
        store.review(lid, "Sam")
        store.log_decision(f"Decision {n}", "Morgan", [lid])
    texts = [i["text"] for i in store.digest("Jo")["items"] if i["kind"] == "moment"]
    assert "That is your 5th checked learning." in texts
    assert "The team's learnings have now informed 5 decisions." in texts
