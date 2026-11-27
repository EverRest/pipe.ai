from types import SimpleNamespace as NS

from pipe.core.claim import claim_excluded, resolve_claim, ts_key


def c(ts, by, status="claimed"):
    return NS(ts=ts, by=by, status=status)


def test_lowest_ts_wins_any_order():
    a, b = c("1700000000.000900", "A"), c("1700000000.001000", "B")
    assert resolve_claim([a, b]) is a
    assert resolve_claim([b, a]) is a


def test_ts_is_numeric():
    assert ts_key("999.000001") < ts_key("1000.000001")
    a, b = c("999.000001", "B"), c("1000.000001", "A")
    assert resolve_claim([b, a]) is a


def test_equal_ts_lower_by_wins():
    a, b = c("5.000001", "A"), c("5.000001", "B")
    assert resolve_claim([b, a]) is a


def test_failed_dropped_and_empty():
    assert resolve_claim([c("1.000001", "A", "failed")]) is None
    assert resolve_claim([]) is None
    ok = c("2.000001", "B")
    assert resolve_claim([c("1.000001", "A", "failed"), ok]) is ok


def test_input_not_changed():
    xs = [c("3.000001", "C"), c("1.000001", "A"), c("2.000001", "B")]
    before = list(xs)
    assert resolve_claim(xs).by == "A"
    assert xs == before


def test_claim_excluded():
    step = NS(exclude_agents_of=(0, 2))
    holder = {0: "A", 2: "C"}.get
    assert claim_excluded(step, "A", holder)
    assert claim_excluded(step, "C", holder)
    assert not claim_excluded(step, "B", holder)
    assert not claim_excluded(NS(exclude_agents_of=None), "A", holder)
    assert not claim_excluded(step, "A", lambda j: None)  # holder unknown
