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


def test_proyecto_dentro_de_una_carpeta_build_se_analiza(tmp_path):
    from quietfail.cli import _scan_path

    proj = tmp_path / "build" / "proyecto"
    proj.mkdir(parents=True)
    (proj / "x.sh").write_text('#!/bin/bash\ncp a b || echo "ERROR: fallo"\n')
    (proj / "venv").mkdir()
    (proj / "venv" / "y.sh").write_text('#!/bin/bash\ncp a b || echo "ERROR: fallo"\n')   # este sí se salta
    findings, _ = _scan_path(proj, ("ERROR",))
    assert [f.path.endswith("x.sh") for f in findings] == [True]


def test_fichero_ilegible_se_avisa(tmp_path):
    import os

    import pytest

    if os.geteuid() == 0:
        pytest.skip("root lee cualquier fichero")
    from quietfail.cli import _scan_path

    f = tmp_path / "x.sh"
    f.write_text('#!/bin/bash\necho "ERROR"\n')
    f.chmod(0)
    try:
        _, skipped = _scan_path(tmp_path, ("ERROR",))
        assert skipped and "no se puede leer" in skipped[0][1]
    finally:
        f.chmod(0o644)
