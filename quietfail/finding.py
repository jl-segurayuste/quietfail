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
