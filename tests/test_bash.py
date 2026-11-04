from pathlib import Path

import pytest

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


def test_syntax_error_se_informa_en_vez_de_pasar_por_limpio(tmp_path):
    import pytest

    from quietfail.finding import Unparseable
    broken = tmp_path / "broken.sh"
    broken.write_text("if [ 1 -eq 1 then echo oops\n")
    with pytest.raises(Unparseable, match="parcial"):
        scan_file(broken)


def test_error_de_sintaxis_no_impide_analizar_el_resto(tmp_path):
    """tree-sitter se recupera: lo que se pudo leer se analiza y llega en la excepción."""
    import pytest

    from quietfail.finding import Unparseable
    script = tmp_path / "mixto.sh"
    script.write_text('#!/bin/bash\nif true; then\n  echo "ERROR: algo"\nfi\nfoo() { ( ; }\n')
    with pytest.raises(Unparseable) as e:
        scan_file(script, keywords=("ERROR",))
    assert [f.line for f in e.value.findings] == [3]


@pytest.mark.parametrize("script", [
    # construcciones que bashlex no sabía leer (2 de cada 3 scripts reales se descartaban)
    'if [[ -f /etc/x && $EUID -ne 0 ]]; then\n  echo "ERROR: falta x"\nfi\n',
    'n=$(( $# + 1 ))\nif [ "$n" -gt 2 ]; then\n  echo "ERROR: $(( n * 2 ))"\nfi\n',
    "cat <<'EOF' > /tmp/x\nhola\nEOF\nif true; then\n  echo \"ERROR: x\"\nfi\n",
    'time du -sh /var/log\nif true; then\n  echo "ERROR: y" >&2\nfi\n',
])
def test_construcciones_de_bash_reales(tmp_path, script):
    path = tmp_path / "real.sh"
    path.write_text("#!/bin/bash\n" + script)
    findings = scan_file(path, keywords=("ERROR",))
    assert len(findings) == 1 and "ERROR" in findings[0].snippet


def test_case_y_grupos_con_llaves(tmp_path):
    path = tmp_path / "opciones.sh"
    path.write_text(
        "#!/bin/bash\n"
        'case "$1" in\n'
        '  start) run ;;\n'
        '  *) echo "ERROR: opción desconocida" ;;\n'          # sin exit: fallo silencioso
        'esac\n'
        'cmd || { echo "ERROR: cmd falló"; exit 1; }\n'        # con exit: bien
        'cmd2 || { echo "FAIL: cmd2"; }\n'                     # sin exit
    )
    findings = scan_file(path)
    assert sorted(f.line for f in findings) == [4, 7]


def test_variables_y_opciones_no_son_el_mensaje(tmp_path):
    """Falsos positivos reales: `${failed}` contaba como FAILED y `--critical` como CRITICAL."""
    path = tmp_path / "informe.sh"
    path.write_text(
        "#!/bin/bash\n"
        'echo "  SSH fallidos (24h): ${failed:-?}"\n'
        'echo "Usage: $0 -w|--warning <warn> -c|--critical <crit>"\n'
        'echo "estado: $(systemctl is-failed x)"\n'
        'echo "ERROR de verdad: $failed"\n'
    )
    assert [f.line for f in scan_file(path)] == [5]


@pytest.mark.parametrize("line", [
    'echo "ERROR: falló la copia" | tee -a "$LOG"',
    'echo >&2 "ERROR: redirección delante"',
    'printf "ERROR: %s\\n" "$f" 2>&1 | logger -t backup',
])
def test_flags_pipeline_and_leading_redirect(tmp_path, line):
    script = tmp_path / "s.sh"
    script.write_text(f"#!/bin/bash\ncp a b\n{line}\n")
    assert len(scan_file(script)) == 1


def test_pipeline_followed_by_exit_is_fine(tmp_path):
    script = tmp_path / "s.sh"
    script.write_text('#!/bin/bash\necho "ERROR: x" | tee -a log\nexit 1\n')
    assert scan_file(script) == []
