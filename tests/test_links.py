import pytest

from anchor.core import CoreError


def _three(store):
    a = store.propose("Mobile checkout conversion is 42 percent", "data_point", "Ana")["finding"]["id"]
    b = store.propose("Users abandon checkout at the address form", "hypothesis", "Jo")["finding"]["id"]
    c = store.propose("People quit checkout on the address step", "hypothesis", "Kim")["finding"]["id"]
    return a, b, c


def test_links_show_from_both_sides_grouped_by_type(store):
    a, b, c = _three(store)
    store.link(a, b, "supports", "Sam")
    store.link(c, b, "duplicates", "Sam", "Same observation, different study")
    d = store.propose("Autofill would fix the address step", "hypothesis", "Jo")["finding"]["id"]
    store.link(d, b, "extends", "Jo")

    fb = store.get(b)
    assert [e["id"] for e in fb["evidence"]] == [a]  # supports reads as evidence
    assert fb["links"]["duplicates"][0]["finding"]["id"] == c
    assert fb["links"]["duplicates"][0]["note"] == "Same observation, different study"
    assert fb["links"]["extended_by"][0]["finding"]["id"] == d
    assert [e["id"] for e in store.get(a)["cited_by"]] == [b]
    assert store.get(c)["links"]["duplicates"][0]["finding"]["id"] == b
    assert store.get(d)["links"]["extends"][0]["finding"]["id"] == b
    assert [e["kind"] for e in store.history(b)].count("linked") == 3


def test_contradicts_goes_through_the_conflict_flow(store):
    a, b, _ = _three(store)
    store.validate(b, "Sam")
    x = store.propose("Address form length does not affect checkout", "hypothesis", "Al")["finding"]["id"]
    r = store.link(x, b, "contradicts", "Lee", "A/B test disagrees")
    assert [f["status"] for f in r["findings"]] == ["contested", "contested"]
    assert store.get(b)["conflicts"][0]["with"]["id"] == x


def test_link_rules(store):
    a, b, c = _three(store)
    with pytest.raises(CoreError):
        store.link(a, a, "extends", "Sam")
    with pytest.raises(CoreError):
        store.link(a, b, "blocks", "Sam")
    with pytest.raises(CoreError):
        store.link(a, 99, "extends", "Sam")
    store.link(b, c, "duplicates", "Sam")
    with pytest.raises(CoreError):
        store.link(c, b, "duplicates", "Sam")  # same pair from the other side
    store.link(a, b, "supports", "Sam")
    with pytest.raises(CoreError):
        store.link(a, b, "supports", "Sam")
