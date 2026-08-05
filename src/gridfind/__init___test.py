from gridfind import Verdict, verdict


def test_public_api_exposes_verdict_end_to_end():
    result = verdict(["board"], "stack: board\ngiven R1C1 5\n")

    assert isinstance(result, Verdict)
    assert result.kind == "found"
