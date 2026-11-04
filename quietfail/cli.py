from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .finding import Finding, Unparseable
from .keywords import DEFAULT_KEYWORDS
from .scanners import bash, cron, github_actions, systemd

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}


def _iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        # Solo cuentan las carpetas por debajo de la raíz analizada: con la ruta absoluta, un proyecto
        # dentro de una carpeta llamada «build» o «venv» se saltaba entero («sin hallazgos»).
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def _scan_path(root: Path, keywords: tuple[str, ...]) -> tuple[list[Finding], list[tuple[Path, str]]]:
    findings: list[Finding] = []
    skipped: list[tuple[Path, str]] = []
    for path in _iter_files(root):
        try:
            if bash.looks_like_shell_script(path):
                findings.extend(bash.scan_file(path, keywords=keywords))
            elif systemd.looks_like_unit_file(path):
                findings.extend(systemd.scan_file(path))
            elif cron.looks_like_crontab(path):
                findings.extend(cron.scan_file(path))
            elif path.name.endswith((".yml", ".yaml")) and ".github/workflows" in str(path):
                findings.extend(github_actions.scan_file(path))
        except Unparseable as e:
            findings.extend(e.findings)
            skipped.append((path, str(e)))
        except (OSError, UnicodeDecodeError) as e:
            # Un fichero que no se puede leer es un hueco del análisis: se avisa, no se calla
            skipped.append((path, f"no se puede leer: {e.strerror if isinstance(e, OSError) else e}"))
    return findings, skipped


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quietfail",
        description=(
            "Encuentra scripts, unidades systemd, crontabs y workflows de CI "
            "que registran un error pero terminan en éxito de todas formas."
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="Fichero o directorio a analizar")
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help=f"Palabra clave de error adicional (repetible). Por defecto: {', '.join(DEFAULT_KEYWORDS)}",
    )
    parser.add_argument("--quiet", action="store_true", help="Solo imprime si hay hallazgos")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    keywords = DEFAULT_KEYWORDS
    if args.keywords:
        keywords = tuple(keywords) + tuple(k.upper() for k in args.keywords)

    root = Path(args.path)
    if not root.exists():
        print(f"quietfail: no existe la ruta '{root}'", file=sys.stderr)
        return 2

    findings, skipped = _scan_path(root, keywords)
    for path, reason in skipped:          # siempre, también con --quiet: es un hueco del análisis
        print(f"quietfail: no se pudo analizar {path}: {reason}", file=sys.stderr)

    if not findings:
        if not args.quiet:
            print("quietfail: sin hallazgos.")
        return 0

    for f in sorted(findings, key=lambda f: (f.path, f.line)):
        print(f.format())
    print(f"\n{len(findings)} posible(s) fallo(s) silencioso(s) encontrado(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
