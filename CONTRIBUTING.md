# Contribuir

## Añadir un scanner nuevo

Cada formato (bash, systemd, cron, GitHub Actions...) vive como un módulo
independiente en `quietfail/scanners/`, con dos funciones: `scan_file(path)
-> list[Finding]` y una función `looks_like_*(path)` que decide si un
fichero pertenece a ese scanner. Añade el módulo, sus tests en `tests/`, y
una entrada en el dispatcher de `cli.py::_scan_path`.

## Antes de mandar un PR

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

- Cualquier detección nueva o corregida necesita sus propios tests, tanto
  un caso que debe marcarse como uno que no debe marcarse (falso positivo).
- Si tu cambio puede introducir falsos positivos, dilo explícitamente en el
  mensaje del `Finding`, no lo dejes implícito.
- `ruff check .` sin avisos.

## Reportar un falso positivo

El mínimo para poder reproducirlo: el fragmento de script/config concreto
que lo dispara, no hace falta el repositorio entero.
