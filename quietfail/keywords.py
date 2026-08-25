"""Palabras clave que marcan un mensaje como 'esto fue un error'.

Deliberadamente conservador por defecto: solo términos que casi siempre
significan que algo salió mal, no ruido como WARN/AVISO que a menudo son
solo informativos. Se puede ampliar con --keyword.
"""

from __future__ import annotations

import re

DEFAULT_KEYWORDS = ("ERROR", "CRITICAL", "FATAL", "FAIL", "FAILED")

# Comandos cuyo primer argumento de texto se interpreta como un mensaje
# a inspeccionar en busca de palabras clave de error.
LOG_COMMANDS = frozenset({"echo", "printf", "logger", "log", "print"})


def build_keyword_regex(keywords: tuple[str, ...] = DEFAULT_KEYWORDS) -> re.Pattern[str]:
    escaped = [re.escape(k) for k in keywords]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


def message_looks_like_error(text: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(text))
