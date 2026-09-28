import pytest

from anchor.core import CoreError


def _three(store):
    a = store.add("Mobile checkout conversion is 42 percent", "observation", "Ana")["learning"]["id"]
    b = store.add("Users abandon checkout at the address form", "finding", "Jo")["learning"]["id"]
    c = store.add("People quit checkout on the address step", "finding", "Kim")["learning"]["id"]
    return a, b, c


def test_links_show_from_both_sides_grouped_by_type(store):
    a, b, c = _three(store)
    store.link(a, b, "supports", "Sam")
    store.link(c, b, "same_as", "Sam", "Same pattern, different study")
    d = store.add("Autofill would fix the address step", "finding", "Jo")["learning"]["id"]
    store.link(d, b, "builds_on", "Jo")

    fb = store.get(b)
    assert [e["id"] for e in fb["evidence"]] == [a]  # supports reads as evidence
    assert fb["links"]["same_as"][0]["learning"]["id"] == c
    assert fb["links"]["same_as"][0]["note"] == "Same pattern, different study"
    assert fb["links"]["built_on_by"][0]["learning"]["id"] == d
    assert fb["connections"] == 3
    assert [e["id"] for e in store.get(a)["supports"]] == [b]
    assert store.get(c)["links"]["same_as"][0]["learning"]["id"] == b
    assert store.get(d)["links"]["builds_on"][0]["learning"]["id"] == b
    assert [e["kind"] for e in store.history(b)].count("linked") == 3


def test_conflicts_with_contests_both(store):
    _, b, _ = _three(store)
    store.review(b, "Sam")
    x = store.add("Address form length does not affect checkout", "finding", "Al")["learning"]["id"]
    r = store.link(x, b, "conflicts_with", "Lee", "A/B test disagrees")
    assert [f["chip"]["label"] for f in r["learnings"]] == ["Contested", "Contested"]
    assert store.get(b)["conflicts"][0]["with"]["id"] == x


def test_link_rules(store):
    a, b, c = _three(store)
    with pytest.raises(CoreError):
        store.link(a, a, "builds_on", "Sam")
    with pytest.raises(CoreError):
        store.link(a, b, "blocks", "Sam")
    with pytest.raises(CoreError):
        store.link(a, 99, "builds_on", "Sam")
    store.link(b, c, "same_as", "Sam")
    with pytest.raises(CoreError):
        store.link(c, b, "same_as", "Sam")  # same pair from the other side
    store.link(a, b, "supports", "Sam")
    with pytest.raises(CoreError):
        store.link(a, b, "supports", "Sam")
