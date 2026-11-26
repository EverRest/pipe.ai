from pipe.core.dedupe import remember


def test_adds_and_keeps_last_500():
    keys = [str(i) for i in range(500)]
    out = remember(keys, "new")
    assert len(out) == 500 and out[-1] == "new" and out[0] == "1"


def test_input_unchanged_and_no_dup():
    keys = ["a"]
    assert remember(keys, "b") == ["a", "b"]
    assert keys == ["a"]
    assert remember(keys, "a") == ["a"]
