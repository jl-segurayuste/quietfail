"""Detecta líneas de crontab que silencian salida y error por completo.

Patrón: `>/dev/null 2>&1` (o `&>/dev/null`) sin ningún mecanismo visible de
notificación (curl/wget a un servicio de heartbeat, `mail`, etc.) a
continuación en la misma línea. Si el comando falla, nadie se entera nunca
— ni por email de cron (que también se ha silenciado), ni por ningún otro
canal.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..finding import Finding

_CRON_LINE_RE = re.compile(
    r"^\s*(?:@\w+|(?:\S+\s+){5})(?P<command>.+)$"
)
_FULL_SILENCE_RE = re.compile(r"(>\s*/dev/null\s+2>&1)|(&>\s*/dev/null)|(>\s*/dev/null\s+2>/dev/null)")
_HEARTBEAT_HINT_RE = re.compile(
    r"(curl|wget)\s+.*(healthcheck|heartbeat|cronitor|deadmanping|cronping|hc-ping|betteruptime)",
    re.IGNORECASE,
)
_COMMENT_OR_BLANK_RE = re.compile(r"^\s*(#.*)?$")


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = path.read_text(errors="replace").splitlines()

    for lineno, raw in enumerate(lines, start=1):
        if _COMMENT_OR_BLANK_RE.match(raw):
            continue
        m = _CRON_LINE_RE.match(raw)
        if not m:
            continue
        command = m.group("command")
        if _FULL_SILENCE_RE.search(command) and not _HEARTBEAT_HINT_RE.search(command):
            findings.append(
                Finding(
                    scanner="cron",
                    path=str(path),
                    line=lineno,
                    message=(
                        "silencia stdout y stderr por completo sin ningún heartbeat/ping "
                        "posterior — si el comando falla, no hay forma de enterarse"
                    ),
                    snippet=raw.strip(),
                )
            )

    return findings


def looks_like_crontab(path: Path) -> bool:
    if path.name == "crontab" or path.suffix == ".crontab":
        return True
    return "cron" in str(path.parent).lower() and path.suffix == ""
