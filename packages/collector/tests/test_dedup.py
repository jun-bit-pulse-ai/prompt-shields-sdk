from collector.dedup import compute_confidence


def test_confidence_single_sdk():
    assert compute_confidence(["sdk"]) == "high"

def test_confidence_single_browser():
    assert compute_confidence(["browser_extension"]) == "medium"

def test_confidence_single_survey():
    assert compute_confidence(["survey"]) == "low"

def test_confidence_multiple_sources():
    assert compute_confidence(["sdk", "browser_extension"]) == "verified"

def test_confidence_empty():
    assert compute_confidence([]) == "low"
