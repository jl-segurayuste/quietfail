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


def test_prefijo_menos_y_or_true_dentro_de_sh_c(tmp_path):
    from quietfail.scanners.systemd import scan_file

    unit = tmp_path / "b.service"
    unit.write_text(
        "[Service]\n"
        "ExecStartPre=-/usr/bin/rm -f /run/b.lock\n"       # paso opcional: no se marca
        "ExecStart=-/usr/local/bin/backup.sh\n"            # 3
        "ExecStartPost=/bin/sh -c \"mount /mnt/bk || true\"\n"   # 4
        "ExecStopPost=/bin/bash -c 'rsync -a /a /b || :'\n"
    )
    assert [f.line for f in scan_file(unit)] == [3, 4]
