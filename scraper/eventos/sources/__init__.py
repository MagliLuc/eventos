"""Fuentes de datos. Cada una devuelve una lista de `Event` normalizados.

La lista de qué se consulta vive en `scraper/sources.json`, no acá: ver
`eventos.registry`. Este módulo solo expone los tipos de extractor.
"""
from .base import Source, http_session
from .ba_data import BaDataSource
from .feeds import IcsSource, RssSource, TribeEventsSource
from .html_source import HtmlAgendaSource
from .local_seed import LocalSeedSource

__all__ = [
    "Source",
    "http_session",
    "BaDataSource",
    "HtmlAgendaSource",
    "IcsSource",
    "RssSource",
    "TribeEventsSource",
    "LocalSeedSource",
]
