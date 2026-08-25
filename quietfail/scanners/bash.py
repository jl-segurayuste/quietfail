"""Detecta el patrón: una rama registra un error pero no propaga el fallo.

Enfoque deliberadamente estrecho (igual que staleif): en vez de intentar
un análisis de flujo de control completo, solo mira el *bloque inmediato*
que contiene el mensaje de error (el cuerpo del if/elif/else, el bucle, la
función o el nivel superior del script) y comprueba si ese mismo bloque
contiene, después del mensaje, un `exit`/`return` cuyo código no sea
literalmente 0. No sigue el fallo a bloques exteriores ni evalúa
variables — eso da falsos negativos en casos complejos, pero mantiene el
check 100% mecánico y sin falsos positivos por ambigüedad de flujo.
"""

from __future__ import annotations

import re
from pathlib import Path

import bashlex
from bashlex import ast as bashlex_ast

from ..finding import Finding
from ..keywords import DEFAULT_KEYWORDS, LOG_COMMANDS, build_keyword_regex, message_looks_like_error

_BRANCH_KEYWORDS = {"then", "else"}
_IF_BOUNDARY_KEYWORDS = {"if", "elif", "then", "else", "fi"}


def _line_of(pos: tuple[int, int], source: str) -> int:
    return source.count("\n", 0, pos[0]) + 1


def _word_text(node: bashlex_ast.node) -> str:
    return getattr(node, "word", "")


def _is_command(node: bashlex_ast.node) -> bool:
    return getattr(node, "kind", None) == "command"


def _command_words(node: bashlex_ast.node) -> list[str]:
    return [_word_text(p) for p in getattr(node, "parts", []) if getattr(p, "kind", None) == "word"]


def _exit_arg(node: bashlex_ast.node) -> str | None:
    """Si `node` es un `exit`/`return`, devuelve su argumento (o '' si no tiene)."""
    if not _is_command(node):
        return None
    words = _command_words(node)
    if not words or words[0] not in ("exit", "return"):
        return None
    return words[1] if len(words) > 1 else ""


def _is_protective_exit(arg: str | None) -> bool:
    """True si este exit/return SÍ propaga el fallo (o no podemos estar seguros de que no)."""
    if arg is None:
        return False
    if arg == "":
        # `exit` a secas hereda $? de lo anterior — asumimos que puede ser
        # no-cero (beneficio de la duda, evita falsos positivos).
        return True
    try:
        return int(arg) != 0
    except ValueError:
        # Argumento dinámico ($?, $RESULT...) — no evaluable estáticamente,
        # mismo criterio: asumir que puede propagar el fallo.
        return True


def _extract_statements(node: bashlex_ast.node) -> list[bashlex_ast.node]:
    """De un nodo 'list' (secuencia separada por ; && || \\n), extrae solo
    los nodos de sentencia (descarta los OperatorNode que los separan)."""
    if node is None:
        return []
    if getattr(node, "kind", None) == "list":
        return [p for p in node.parts if getattr(p, "kind", None) != "operator"]
    return [node]


def _if_branches(if_node: bashlex_ast.node) -> list[list[bashlex_ast.node]]:
    """Extrae los cuerpos then/elif/else de un IfNode como bloques separados."""
    branches: list[list[bashlex_ast.node]] = []
    parts = if_node.parts
    i = 0
    while i < len(parts):
        p = parts[i]
        if getattr(p, "kind", None) == "reservedword" and _word_text(p) in ("then", "else"):
            body = parts[i + 1] if i + 1 < len(parts) else None
            if body is not None and not (
                getattr(body, "kind", None) == "reservedword" and _word_text(body) in _IF_BOUNDARY_KEYWORDS
            ):
                branches.append(_extract_statements(body))
        i += 1
    return branches


def _top_level_blocks(script: str) -> list[list[bashlex_ast.node]]:
    trees = bashlex.parse(script)
    statements: list[bashlex_ast.node] = []
    for tree in trees:
        if getattr(tree, "kind", None) == "compound" and getattr(tree, "list", None):
            statements.extend(tree.list)
        else:
            statements.append(tree)
    return [statements]


def _unwrap_compound(node: bashlex_ast.node) -> bashlex_ast.node:
    """'compound' es solo un envoltorio genérico de sentencia (lo usa
    bashlex tanto para "esto es un if/for/while/function como sentencia"
    como para el propio `{ ... }` de un cuerpo de función) — el nodo con
    kind real ('if', 'for'...) vive en .list[0] cuando el envoltorio
    representa una sola sentencia."""
    if getattr(node, "kind", None) == "compound":
        inner = getattr(node, "list", None) or []
        if len(inner) == 1:
            return inner[0]
    return node


def _brace_group_statements(compound_node: bashlex_ast.node) -> list[bashlex_ast.node]:
    """Extrae las sentencias de un grupo `{ ... }` (cuerpo de función),
    descartando las llaves reservedword y aplanando la lista interior."""
    inner = getattr(compound_node, "list", None) or []
    statements: list[bashlex_ast.node] = []
    for item in inner:
        if getattr(item, "kind", None) == "reservedword" and _word_text(item) in ("{", "}"):
            continue
        statements.extend(_extract_statements(item))
    return statements


def _nested_blocks(node: bashlex_ast.node) -> list[list[bashlex_ast.node]]:
    """Bloques anidados dentro de este nodo (ramas de if, cuerpos de
    función/bucle) a inspeccionar recursivamente."""
    node = _unwrap_compound(node)
    kind = getattr(node, "kind", None)
    blocks: list[list[bashlex_ast.node]] = []
    if kind == "if":
        blocks.extend(_if_branches(node))
    elif kind == "function":
        for p in getattr(node, "parts", []):
            if getattr(p, "kind", None) == "compound":
                blocks.append(_brace_group_statements(p))
    elif kind in ("for", "while", "until"):
        for p in getattr(node, "parts", []):
            if getattr(p, "kind", None) == "list":
                blocks.append(_extract_statements(p))
    return blocks


def _scan_block(
    statements: list[bashlex_ast.node],
    source: str,
    path: str,
    pattern: re.Pattern[str],
) -> list[Finding]:
    findings: list[Finding] = []

    for idx, stmt in enumerate(statements):
        if _is_command(stmt):
            words = _command_words(stmt)
            if words and words[0] in LOG_COMMANDS:
                message = " ".join(words[1:])
                if message_looks_like_error(message, pattern):
                    protected = any(
                        _is_protective_exit(_exit_arg(later)) for later in statements[idx + 1 :]
                    )
                    if not protected:
                        line = _line_of(stmt.pos, source)
                        snippet = source.splitlines()[line - 1].strip()
                        findings.append(
                            Finding(
                                scanner="bash",
                                path=path,
                                line=line,
                                message=(
                                    f"registra un mensaje de error ('{message.strip()[:60]}') "
                                    "pero este bloque no termina en exit/return con código != 0"
                                ),
                                snippet=snippet,
                            )
                        )

        # recursión: cualquier bloque anidado dentro de esta sentencia
        for nested in _nested_blocks(stmt):
            findings.extend(_scan_block(nested, source, path, pattern))

    return findings


def scan_file(path: Path, keywords: tuple[str, ...] = DEFAULT_KEYWORDS) -> list[Finding]:
    source = path.read_text(errors="replace")
    pattern = build_keyword_regex(keywords)
    try:
        blocks = _top_level_blocks(source)
    except bashlex.errors.ParsingError:
        return []

    findings: list[Finding] = []
    for block in blocks:
        findings.extend(_scan_block(block, source, str(path), pattern))
    return findings


def looks_like_shell_script(path: Path) -> bool:
    if path.suffix in (".sh", ".bash"):
        return True
    if path.suffix:
        return False
    try:
        with path.open("rb") as f:
            first_line = f.readline(200)
    except OSError:
        return False
    return first_line.startswith(b"#!") and (b"sh" in first_line)
