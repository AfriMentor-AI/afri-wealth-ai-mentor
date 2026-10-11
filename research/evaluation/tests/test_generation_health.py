from evaluation.generation_health import health_report, is_degenerate

GOOD = ("Raise prices ten percent this week and tell your regulars why. Track daily sales for seven days "
        "so you can see whether volume drops. What is your current margin on flour?")


def test_normal_answer_is_healthy():
    assert is_degenerate(GOOD) == (False, "")


def test_the_actual_c4_collapse_is_caught():
    bad = "what do we friend friend — what is the friend " + "friend " * 40
    assert is_degenerate(bad)[0]


def test_empty_and_runaway_are_caught():
    assert is_degenerate("")[0] and is_degenerate("   ")[0]
    assert is_degenerate(" ".join(f"w{i}" for i in range(500)))[1] == "ran to the length cap"


def test_report_blocks_a_mostly_degenerate_adapter_but_tolerates_one_bad_sample():
    ok = [GOOD] * 9 + ["friend " * 30]
    assert health_report(ok)["healthy"]
    assert not health_report([GOOD] * 6 + ["friend " * 30] * 4)["healthy"]
    assert not health_report([])["healthy"]
