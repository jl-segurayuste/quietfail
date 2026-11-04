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


def test_or_exit_0_y_linea_correcta(tmp_path):
    from quietfail.scanners.github_actions import scan_file

    wf = tmp_path / "ci.yml"
    wf.write_text(
        "jobs:\n  t:\n    steps:\n"
        "      - run: |\n          make test || true\n          echo fin\n"
        "      - run: make lint || exit 0\n"
        "      - run: \"make doc || :\"\n"
    )
    assert [f.line for f in scan_file(wf)] == [5, 7, 8]


def test_step_sin_nombre_se_identifica_por_su_numero(tmp_path):
    wf = tmp_path / ".github" / "workflows" / "ci.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("on: push\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: echo hola\n"
                  "      - run: pytest || true\n")
    [finding] = scan_file(wf)
    assert "'n.º 2'" in finding.message
