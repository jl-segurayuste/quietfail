from pathlib import Path

from quietfail.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_exits_nonzero_on_findings(capsys):
    code = main([str(FIXTURES / "bad_backup.sh")])
    out = capsys.readouterr().out
    assert code == 1
    assert "bad_backup.sh" in out


def test_cli_exits_zero_on_clean_file(capsys):
    code = main([str(FIXTURES / "good_backup.sh")])
    assert code == 0


def test_cli_missing_path_exits_2():
    code = main(["/does/not/exist"])
    assert code == 2


def test_cli_extra_keyword_flag(capsys):
    code = main([str(FIXTURES / "bad.crontab"), "--keyword", "unused"])
    assert code == 1
