"""Fuentes de datos. Cada una devuelve una lista de `Event` normalizados."""
from .base import Source, http_session
from .palacio_libertad import PalacioLibertadSource
from .usina_del_arte import UsinaDelArteSource
from .ba_turismo import BuenosAiresTurismoSource
from .local_seed import LocalSeedSource

ALL_SOURCES: list[Source] = [
    PalacioLibertadSource(),
    UsinaDelArteSource(),
    BuenosAiresTurismoSource(),
]

__all__ = [
    "Source",
    "http_session",
    "ALL_SOURCES",
    "LocalSeedSource",
    "PalacioLibertadSource",
    "UsinaDelArteSource",
    "BuenosAiresTurismoSource",
]
