"""Allowlist: both the sender and the thread starter must be trusted (DQ2)."""

from delegation_kit import CH, Rig, meta
from thread_kit import TOP


def status(r):
    r.handoff(r.seed(starter=r.starter))
    return meta(r.gate())["status"]


def run(allowlist, starter="U9"):
    r = Rig(allowlist)
    r.starter = starter
    return status(r), len(r.rt_b.inputs)


def test_sender_and_starter_in_allowlist_run_with_no_button():
    assert run(["B1", "U9"]) == ("done", 1)


def test_sender_listed_and_starter_is_owner_of_the_sender_gets_the_button():
    # OA is neither our owner nor allowlisted: every human in the thread must be
    assert run(["B1"], starter="OA") == ("needs_approval", 0)


def test_sender_listed_and_owner_of_the_sender_allowlisted_runs():
    assert run(["B1", "OA"], starter="OA") == ("done", 1)


def test_sender_listed_but_starter_is_a_stranger_gets_the_button():
    assert run(["B1"]) == ("needs_approval", 0)


def test_starter_listed_but_sender_is_not_gets_the_button():
    assert run(["U9"]) == ("needs_approval", 0)


def test_empty_allowlist_gets_the_button():
    assert run([]) == ("needs_approval", 0)


def test_bot_starter_in_allowlist_is_trusted():
    assert run(["B1", "B7"], starter="B7") == ("done", 1)


def test_untrusted_human_in_thread_blocks_auto():
    r = Rig(["B1", "U9"])
    r.starter = "U9"
    h = r.seed(starter=r.starter)
    r.ta.add_message(CH, "hi", sender_id="U5", thread=TOP)
    r.handoff(h)
    assert meta(r.gate())["status"] == "needs_approval" and not r.rt_b.inputs


def test_untrusted_bot_in_thread_blocks_auto():
    r = Rig(["B1", "U9"])
    r.starter = "U9"
    h = r.seed(starter=r.starter)
    r.ta.add_message(CH, "hi", sender_id="B9", thread=TOP, sender_is_bot=True)
    r.handoff(h)
    assert meta(r.gate())["status"] == "needs_approval" and not r.rt_b.inputs
