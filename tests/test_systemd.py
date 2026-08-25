from pathlib import Path

from quietfail.scanners.systemd import scan_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_flags_exec_start_swallowing_failure():
    findings = scan_file(FIXTURES / "bad.service")
    assert len(findings) == 1
    assert "backup-offsite.sh" in findings[0].snippet


def test_clean_unit_has_no_findings(tmp_path):
    f = tmp_path / "good.service"
    f.write_text("[Service]\nExecStart=/opt/scripts/backup.sh\n")
    assert scan_file(f) == []
