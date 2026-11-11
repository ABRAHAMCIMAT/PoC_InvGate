"""Proveedor simulated: demo persistente pensado para aprobaciones en Teams."""

from __future__ import annotations

from backend.ticketing.demo import DemoProvider


class SimulatedProvider(DemoProvider):
    """Alias del proveedor demo con semántica de simulación para Teams.

    En fases posteriores se añadirá persistencia en archivo y el disparo de
    aprobaciones; por ahora comparte el almacenamiento en memoria.
    """
