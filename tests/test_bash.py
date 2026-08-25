from pathlib import Path

from quietfail.scanners.bash import scan_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_flags_error_without_exit():
    findings = scan_file(FIXTURES / "bad_backup.sh", keywords=("ERROR",))
    assert len(findings) == 1
    assert findings[0].line == 7
    assert "ERROR" in findings[0].snippet


def test_does_not_flag_when_exit_follows():
    findings = scan_file(FIXTURES / "good_backup.sh", keywords=("ERROR",))
    assert findings == []


def test_flags_inside_function_body():
    findings = scan_file(FIXTURES / "nested_function.sh", keywords=("CRITICAL",))
    assert len(findings) == 1
    assert "CRITICAL" in findings[0].snippet


def test_does_not_flag_dynamic_exit_code():
    findings = scan_file(FIXTURES / "dynamic_exit.sh", keywords=("ERROR",))
    assert findings == []


def test_no_keyword_match_means_no_finding():
    findings = scan_file(FIXTURES / "bad_backup.sh", keywords=("SOMETHING_ELSE",))
    assert findings == []


def test_syntax_error_does_not_crash(tmp_path):
    broken = tmp_path / "broken.sh"
    broken.write_text("if [ 1 -eq 1 then echo oops\n")
    findings = scan_file(broken)
    assert findings == []
