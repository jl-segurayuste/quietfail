"""Detecta pasos de GitHub Actions cuyo fallo se descarta sin comprobarlo.

Dos patrones, ambos 100% mecánicos:

1. `continue-on-error: true` en un step con `id:` cuyo `steps.<id>.outcome`
   (o `.conclusion`) nunca se referencia en ningún paso/condición
   posterior del mismo job — el resultado del step se pierde sin más.
2. Un `run:` cuyo comando termina en `|| true` (o `; true`) — silencia
   cualquier fallo incondicionalmente, sin importar la causa.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..finding import Finding, Unparseable

_SWALLOW_RE = re.compile(r"(\|\|\s*true\s*$)|(;\s*true\s*$)", re.MULTILINE)


def _line_of_key(source: str, needle: str, start_from: int = 0) -> int:
    idx = source.find(needle, start_from)
    if idx == -1:
        return 1
    return source.count("\n", 0, idx) + 1


def scan_file(path: Path) -> list[Finding]:
    source = path.read_text(errors="replace")
    try:
        data = yaml.safe_load(source)
    except yaml.YAMLError as e:
        raise Unparseable(f"YAML no válido ({str(e).splitlines()[0]})") from None

    if not isinstance(data, dict):
        return []

    findings: list[Finding] = []
    jobs = data.get("jobs")
    if not isinstance(jobs, dict):
        return findings

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue

        job_text_after: dict[str, str] = {}
        ids_with_continue: list[tuple[str, dict]] = []

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            if step.get("continue-on-error") is True and step.get("id"):
                step_id = step["id"]
                remaining_yaml = yaml.dump(steps[i + 1 :])
                ids_with_continue.append((step_id, step))
                job_text_after[step_id] = remaining_yaml

            run = step.get("run")
            if isinstance(run, str) and _SWALLOW_RE.search(run.strip()):
                line = _line_of_key(source, run.strip().splitlines()[-1][-40:] or run.strip())
                findings.append(
                    Finding(
                        scanner="github_actions",
                        path=str(path),
                        line=line,
                        message=(
                            f"job '{job_name}': el step "
                            f"'{step.get('name', step.get('id', '?'))}' termina en `|| true`/`; true`, "
                            "silencia cualquier fallo del comando incondicionalmente"
                        ),
                        snippet=run.strip().splitlines()[-1],
                    )
                )

        for step_id, step in ids_with_continue:
            remaining = job_text_after[step_id]
            referenced = (f"steps.{step_id}.outcome" in remaining) or (
                f"steps.{step_id}.conclusion" in remaining
            )
            if not referenced:
                line = _line_of_key(source, f"id: {step_id}") or _line_of_key(source, f"id: '{step_id}'")
                findings.append(
                    Finding(
                        scanner="github_actions",
                        path=str(path),
                        line=line,
                        message=(
                            f"job '{job_name}': step '{step_id}' usa continue-on-error pero "
                            f"ningún paso posterior comprueba steps.{step_id}.outcome — "
                            "el fallo se descarta sin más"
                        ),
                        snippet=f"id: {step_id}  # continue-on-error: true",
                    )
                )

    return findings
