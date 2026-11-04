"""Detecta el patrón: una rama registra un error pero no propaga el fallo.

Enfoque deliberadamente estrecho (igual que staleif): en vez de intentar
un análisis de flujo de control completo, solo mira el *bloque inmediato*
que contiene el mensaje de error (el cuerpo del if/elif/else, una rama de
case, el bucle, la función, un grupo `{ ...; }` o subshell, o el nivel
superior del script) y comprueba si ese mismo bloque contiene, después del
mensaje, un `exit`/`return` cuyo código no sea literalmente 0. No sigue el
fallo a bloques exteriores ni evalúa variables — eso da falsos negativos en
casos complejos, pero mantiene el check 100% mecánico y sin falsos
positivos por ambigüedad de flujo.

El análisis usa tree-sitter-bash. Antes era bashlex, que no entiende
construcciones normales de bash (`[[ ... ]]`, `$(( ))`, heredocs con
'EOF', muchos `case`) y solo podía leer un tercio de los scripts reales;
el resto se descartaba sin avisar. tree-sitter se recupera de los errores:
si el script tiene alguno, se analiza lo que se pudo leer y la CLI avisa
de que el análisis fue parcial.
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_bash
from tree_sitter import Language, Node, Parser

from ..finding import Finding, Unparseable
from ..keywords import DEFAULT_KEYWORDS, LOG_COMMANDS, build_keyword_regex, message_looks_like_error

_PARSER = Parser(Language(tree_sitter_bash.language()))
# Hijos de un bloque que no son sentencias: palabras reservadas, separadores y comentarios
_NOT_STATEMENTS = {"comment"}


def _text(node: Node) -> str:
    return node.text.decode("utf-8", errors="replace")


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _unwrap(node: Node) -> Node:
    """`echo "ERROR" >&2` es un redirected_statement con el comando dentro."""
    if node.type == "redirected_statement":
        body = node.child_by_field_name("body")
        if body is not None:
            return body
    return node


def _command_words(node: Node) -> list[str]:
    """[nombre, argumentos...] de un `command`; [] si no lo es."""
    if node.type == "pipeline":
        # `echo "ERROR" | tee -a log`: el mensaje es el del primer comando de la tubería
        first = next(iter(node.named_children), None)
        return _command_words(first) if first is not None else []
    extra: list[str] = []
    if node.type == "redirected_statement":
        # `echo >&2 "ERROR: …"`: tree-sitter toma el texto como un destino más de la redirección
        for redirect in node.children_by_field_name("redirect"):
            extra += [_unquote(_text(d)) for d in redirect.children_by_field_name("destination")[1:]]
    node = _unwrap(node)
    if node.type != "command":
        return []
    name = node.child_by_field_name("name")
    if name is None:
        return []
    return [_text(name), *(_unquote(_text(c)) for c in node.children_by_field_name("argument")), *extra]


def _exit_arg(node: Node) -> str | None:
    """Si `node` es un `exit`/`return`, devuelve su argumento (o '' si no tiene)."""
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


def _statements(children: list[Node]) -> list[Node]:
    """Sentencias de una secuencia de nodos; `a && b || c` (list) cuenta como varias."""
    out: list[Node] = []
    for child in children:
        if not child.is_named or child.type in _NOT_STATEMENTS:
            continue
        if child.type == "list":
            out.extend(_statements(child.children))
        else:
            out.append(child)
    return out


def _if_branches(node: Node) -> list[list[Node]]:
    """Cuerpos then/elif/else de un if_statement (o elif_clause) como bloques separados."""
    branches: list[list[Node]] = []
    body: list[Node] | None = None
    for child in node.children:
        if child.type == "then":
            body = []
        elif child.type in ("elif_clause", "else_clause", "fi"):
            if body is not None:
                branches.append(_statements(body))
                body = None
            if child.type == "elif_clause":
                branches.extend(_if_branches(child))
            elif child.type == "else_clause":
                branches.append(_statements(child.children[1:]))
        elif body is not None:
            body.append(child)
    if body is not None:                      # elif_clause: su cuerpo llega hasta el final
        branches.append(_statements(body))
    return branches


def _case_branches(node: Node) -> list[list[Node]]:
    """Cuerpo de cada rama de un case: lo que va después del `)` del patrón."""
    branches: list[list[Node]] = []
    for item in node.children:
        if item.type != "case_item":
            continue
        kids = item.children
        start = next((i for i, c in enumerate(kids) if c.type == ")"), None)
        if start is not None:
            branches.append(_statements(kids[start + 1:]))
    return branches


def _nested_blocks(node: Node) -> list[list[Node]]:
    """Bloques anidados dentro de esta sentencia, a inspeccionar recursivamente."""
    node = _unwrap(node)
    if node.type == "if_statement":
        return _if_branches(node)
    if node.type == "case_statement":
        return _case_branches(node)
    if node.type in ("function_definition", "for_statement", "c_style_for_statement", "while_statement"):
        body = node.child_by_field_name("body")
        return _nested_blocks(body) if body is not None else []
    if node.type in ("compound_statement", "subshell", "do_group"):
        return [_statements(node.children)]
    return []


def _scan_block(statements: list[Node], source: str, path: str, pattern: re.Pattern[str]) -> list[Finding]:
    findings: list[Finding] = []
    lines = source.splitlines()

    for idx, stmt in enumerate(statements):
        words = _command_words(stmt)
        if words and words[0] in LOG_COMMANDS:
            args = words[1:]
            while args and args[0].startswith("-"):        # echo -e, printf --, logger -t …
                args = args[1:]
            message = " ".join(args)
            if message_looks_like_error(message, pattern):
                protected = any(_is_protective_exit(_exit_arg(later)) for later in statements[idx + 1:])
                if not protected:
                    line = stmt.start_point[0] + 1
                    findings.append(
                        Finding(
                            scanner="bash",
                            path=path,
                            line=line,
                            message=(
                                f"registra un mensaje de error ('{message.strip()[:60]}') "
                                "pero este bloque no termina en exit/return con código != 0"
                            ),
                            snippet=lines[line - 1].strip() if line <= len(lines) else "",
                        )
                    )

        # recursión: cualquier bloque anidado dentro de esta sentencia
        for nested in _nested_blocks(stmt):
            findings.extend(_scan_block(nested, source, path, pattern))

    return findings


def _first_error(node: Node) -> Node | None:
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        if child.has_error:
            found = _first_error(child)
            if found is not None:
                return found
    return None


def scan_file(path: Path, keywords: tuple[str, ...] = DEFAULT_KEYWORDS) -> list[Finding]:
    source = path.read_text(errors="replace")
    pattern = build_keyword_regex(keywords)
    tree = _PARSER.parse(source.encode("utf-8"))
    findings = _scan_block(_statements(tree.root_node.children), source, str(path), pattern)
    if tree.root_node.has_error:
        error = _first_error(tree.root_node)
        line = error.start_point[0] + 1 if error is not None else 0
        raise Unparseable(f"análisis parcial: sintaxis de bash no válida cerca de la línea {line}",
                          findings=findings)
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
