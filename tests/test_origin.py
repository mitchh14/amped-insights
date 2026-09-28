"""Origin and confirm: know when AI drafted a learning, and that a person checked it."""

import pytest

from anchor.core import CoreError


def test_ai_made_learnings_start_as_drafts(store):
    r = store.add("Shoppers abandon checkout because forms are long", "finding", "Jo", origin="person_with_ai")
    f = r["learning"]
    assert (f["origin"], f["stage"], f["chip"]["label"], f["confirmed"]) == ("person_with_ai", "draft", "Draft", None)
    assert "draft until Jo confirms it" in r["warnings"][-1]
    person_made = store.add("Checkout takes 4 steps", "observation", "Jo")["learning"]
    assert person_made["stage"] == "shared"


def test_a_draft_cannot_be_reviewed_asked_about_or_promoted(store):
    lid = store.add("Forms are long", "finding", "Jo", origin="ai_agent")["learning"]["id"]
    with pytest.raises(CoreError, match="draft"):
        store.review(lid, "Sam")
    with pytest.raises(CoreError, match="draft"):
        store.ask_for_review(lid, "Jo", people=["Sam"])
    with pytest.raises(CoreError, match="draft"):
        store.promote(lid, "Jo")


def test_only_the_owner_confirms_and_the_record_keeps_what_changed(store):
    lid = store.add("Shoppers abandon checkout because forms are long", "finding", "Jo",
                    origin="person_with_ai")["learning"]["id"]
    with pytest.raises(CoreError, match="only Jo"):
        store.confirm(lid, "Sam")
    f = store.confirm(lid, "jo", "Shoppers abandon mobile checkout at the address form",
                      note="Checked the quotes; narrowed it")["learning"]
    assert f["stage"] == "shared" and f["chip"]["label"] == "Not reviewed"
    assert f["statement"] == "Shoppers abandon mobile checkout at the address form"
    assert f["confirmed"]["by"] == "Jo" and f["confirmed"]["edited"] is True
    assert f["confirmed"]["before"] == "Shoppers abandon checkout because forms are long"
    assert f["confirmed"]["note"] == "Checked the quotes; narrowed it"
    assert store.history(lid)[-1]["text"] == f"Jo confirmed the AI draft #{lid} and changed its wording"
    with pytest.raises(CoreError, match="not a draft"):
        store.confirm(lid, "Jo")
    store.review(lid, "Sam")  # now open for review


def test_confirm_without_changes_is_recorded_as_untouched(store):
    lid = store.add("x is 1", "observation", "Jo", origin="person_with_ai")["learning"]["id"]
    assert store.confirm(lid, "Jo")["learning"]["confirmed"]["edited"] is False


def test_drafts_wait_on_their_owner(store):
    lid = store.add("Forms are long", "finding", "Jo", origin="person_with_ai")["learning"]["id"]
    assert [d["id"] for d in store.my_queue("Jo")["drafts"]] == [lid]
    step = store.next_step("Jo")["step"]
    assert (step["kind"], step["learning_id"], step["button"]) == ("confirm", lid, "Confirm")


def test_an_ai_revision_asks_reviewers_again_once_confirmed(store):
    lid = store.add("Forms are long", "finding", "Jo")["learning"]["id"]
    store.review(lid, "Sam", "changes", note="Which forms?")
    r = store.revise(lid, "Jo", "Address forms are long on mobile", origin="person_with_ai")
    new = r["learning"]["id"]
    assert r["learning"]["stage"] == "draft" and store.my_queue("Sam")["waiting_on_me"] == []
    store.confirm(new, "Jo")
    assert [w["learning"]["id"] for w in store.my_queue("Sam")["waiting_on_me"]] == [new]
