"""Detecta unidades systemd cuyo ExecStart silencia el fallo directamente.

Patrón: `ExecStart=... || true` (o `|| :`) en el propio fichero de unidad —
por muy mal que le vaya al comando, systemd siempre lo ve como éxito
(`Deactivated successfully`), exactamente el aviso engañoso que systemctl/
journalctl muestran para un job que en realidad no hizo nada.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..finding import Finding

_EXEC_LINE_RE = re.compile(r"^\s*ExecStart(?:Pre|Post)?\s*=\s*(?P<command>.+)$")
_SWALLOW_SUFFIX_RE = re.compile(r"(\|\|\s*true\s*$)|(\|\|\s*:\s*$)")


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(errors="replace").splitlines()

    for lineno, raw in enumerate(lines, start=1):
        m = _EXEC_LINE_RE.match(raw)
        if not m:
            continue
        command = m.group("command").strip()
        if _SWALLOW_SUFFIX_RE.search(command):
            findings.append(
                Finding(
                    scanner="systemd",
                    path=str(path),
                    line=lineno,
                    message=(
                        "ExecStart termina en `|| true`/`|| :` — el servicio siempre se "
                        "reporta como éxito aunque el comando real falle"
                    ),
                    snippet=raw.strip(),
                )
            )

    return findings


def looks_like_unit_file(path: Path) -> bool:
    return path.suffix in (".service", ".timer")
