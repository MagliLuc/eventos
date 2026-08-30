#!/usr/bin/env python3
"""Actualiza docs/events.json con la agenda gratuita de CABA.

Uso:
    python run_scraper.py                 # scrapea y escribe docs/events.json
    python run_scraper.py --days 14       # proximos 14 dias
    python run_scraper.py --offline       # solo seed local (util para tests)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eventos.pipeline import run  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "events.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--days", type=int, default=7,
                        help="ventana de dias a publicar (default: 7)")
    parser.add_argument("--offline", action="store_true",
                        help="no sale a la red; usa solo scraper/seed/")
    args = parser.parse_args()

    print(f"Generando {args.output} (ventana: {args.days} dias)")
    payload = run(
        output=args.output,
        days=args.days,
        sources=[] if args.offline else None,
    )
    print(f"Listo: {len(payload['events'])} eventos publicados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
