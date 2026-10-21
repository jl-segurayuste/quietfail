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


def test_cli_lista_lo_que_no_pudo_analizar_y_sigue(tmp_path, capsys):
    (tmp_path / "medir.sh").write_text("#!/bin/bash\nif [ 1 -eq 1 then echo oops\n")
    (tmp_path / "backup.sh").write_text((FIXTURES / "bad_backup.sh").read_text())
    code = main([str(tmp_path), "--quiet"])
    captured = capsys.readouterr()
    assert code == 1 and "backup.sh" in captured.out           # el resto se sigue analizando
    assert "no se pudo analizar" in captured.err and "medir.sh" in captured.err
