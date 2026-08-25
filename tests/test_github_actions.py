from pathlib import Path

from quietfail.scanners.github_actions import scan_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_flags_unchecked_continue_on_error():
    findings = scan_file(FIXTURES / "bad_workflow.yml")
    messages = [f.message for f in findings]
    assert any("integration" in m and "outcome" in m for m in messages)


def test_does_not_flag_checked_continue_on_error():
    findings = scan_file(FIXTURES / "bad_workflow.yml")
    assert not any("'flaky'" in f.message for f in findings)


def test_flags_or_true_swallow():
    findings = scan_file(FIXTURES / "bad_workflow.yml")
    assert any("|| true" in f.message for f in findings)


def test_non_workflow_yaml_ignored(tmp_path):
    f = tmp_path / "config.yml"
    f.write_text("key: value\n")
    assert scan_file(f) == []
