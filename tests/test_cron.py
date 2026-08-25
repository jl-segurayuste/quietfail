from pathlib import Path

from quietfail.scanners.cron import scan_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_flags_fully_silenced_job():
    findings = scan_file(FIXTURES / "bad.crontab")
    assert len(findings) == 1
    assert "backup.sh" in findings[0].snippet


def test_does_not_flag_job_with_heartbeat():
    findings = scan_file(FIXTURES / "bad.crontab")
    assert not any("sync.sh" in f.snippet for f in findings)


def test_ignores_comments(tmp_path):
    f = tmp_path / "crontab"
    f.write_text("# 0 2 * * * /x.sh >/dev/null 2>&1\n")
    assert scan_file(f) == []
