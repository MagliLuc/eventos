"""Fuentes de datos. Cada una devuelve una lista de `Event` normalizados."""
from .base import Source, http_session
from .ba_data import BaDataSource
from .palacio_libertad import PalacioLibertadSource
from .usina_del_arte import UsinaDelArteSource
from .ba_turismo import BuenosAiresTurismoSource
from .agendas_culturales import (
    CentroCulturalRecoletaSource,
    ComplejoTeatralSource,
    CulturaNacionSource,
    MuseoBellasArtesSource,
)
from .local_seed import LocalSeedSource

# Orden = prioridad ante empate en el dedupe. BA Data va primero porque es
# la unica fuente con datos estructurados y compromiso de actualizacion.
ALL_SOURCES: list[Source] = [
    BaDataSource(),
    PalacioLibertadSource(),
    UsinaDelArteSource(),
    CentroCulturalRecoletaSource(),
    MuseoBellasArtesSource(),
    ComplejoTeatralSource(),
    CulturaNacionSource(),
    BuenosAiresTurismoSource(),
]

__all__ = [
    "Source",
    "http_session",
    "ALL_SOURCES",
    "LocalSeedSource",
    "BaDataSource",
    "PalacioLibertadSource",
    "UsinaDelArteSource",
    "BuenosAiresTurismoSource",
    "CentroCulturalRecoletaSource",
    "MuseoBellasArtesSource",
    "ComplejoTeatralSource",
    "CulturaNacionSource",
]
