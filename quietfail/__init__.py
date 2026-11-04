"""quietfail — encuentra jobs que fallan en silencio.

Escanea scripts bash, unidades systemd, crontabs y workflows de GitHub
Actions en busca de un patrón concreto: algo detectó y registró un error,
pero el job/step/servicio igualmente terminó reportándose como éxito.
"""

__version__ = "0.2.3"
