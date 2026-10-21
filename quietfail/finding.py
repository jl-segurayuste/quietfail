"""Modelo de datos compartido por todos los scanners."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """Un caso detectado de fallo silencioso."""

    scanner: str
    path: str
    line: int
    message: str
    snippet: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.scanner}] {self.message}\n    {self.snippet}"


class Unparseable(Exception):
    """El fichero parece de un tipo que analizamos pero no se pudo leer (entero) su sintaxis.

    Antes se devolvía una lista vacía y el informe parecía limpio: un fichero sin analizar es
    justo el tipo de fallo silencioso que esta herramienta busca. La CLI los lista aparte.
    `findings` trae lo que sí se pudo analizar (análisis parcial)."""

    def __init__(self, reason: str, findings: list[Finding] | None = None) -> None:
        super().__init__(reason)
        self.findings = findings or []
