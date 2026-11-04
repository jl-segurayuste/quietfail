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
# `|| true` / `|| :` / `|| exit 0` al final, también dentro de `sh -c '…'` (systemd no interpreta `||`
# por sí mismo: solo tiene efecto dentro de un shell, y entonces la línea acaba en comilla)
_SWALLOW_SUFFIX_RE = re.compile(r"\|\|\s*(?:true|:|exit\s+0)\s*['\"]?\s*$")
# Prefijo `-` de systemd: ignora el código de salida (puede combinarse con @, :, + y !)
_IGNORE_PREFIX_RE = re.compile(r"^[@:+!]*-")


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(errors="replace").splitlines()

    for lineno, raw in enumerate(lines, start=1):
        m = _EXEC_LINE_RE.match(raw)
        if not m:
            continue
        command = m.group("command").strip()
        # El `-` en ExecStartPre/Post suele ser un paso opcional legítimo; en ExecStart oculta que el
        # propio servicio falló
        is_main = raw.strip().split("=", 1)[0].strip() == "ExecStart"
        if is_main and _IGNORE_PREFIX_RE.match(command):
            findings.append(
                Finding(
                    scanner="systemd",
                    path=str(path),
                    line=lineno,
                    message=(
                        "el prefijo `-` hace que systemd ignore el código de salida — el servicio "
                        "se da por bueno aunque el comando falle"
                    ),
                    snippet=raw.strip(),
                )
            )
        elif _SWALLOW_SUFFIX_RE.search(command):
            findings.append(
                Finding(
                    scanner="systemd",
                    path=str(path),
                    line=lineno,
                    message=(
                        "ExecStart termina en `|| true`/`|| :`/`|| exit 0` — el servicio siempre se "
                        "reporta como éxito aunque el comando real falle"
                    ),
                    snippet=raw.strip(),
                )
            )

    return findings


def looks_like_unit_file(path: Path) -> bool:
    return path.suffix in (".service", ".timer")
