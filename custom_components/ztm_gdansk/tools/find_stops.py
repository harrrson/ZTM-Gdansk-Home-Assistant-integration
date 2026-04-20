"""CLI: find ZTM Gdańsk stop IDs by name fragment.

Usage:
    python -m custom_components.ztm_gdansk.tools.find_stops "brama"
    python -m custom_components.ztm_gdansk.tools.find_stops --all
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from aiohttp import ClientSession

from custom_components.ztm_gdansk.api import ZTMGdanskClient
from custom_components.ztm_gdansk.const import POLISH_CHAR_MAP


def _normalize(s: str) -> str:
    return s.translate(POLISH_CHAR_MAP).lower()


def filter_stops(stops: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    q = _normalize(query)
    return [s for s in stops if q in _normalize(s.get("name", ""))]


def format_row(stop: dict[str, Any]) -> str:
    return f"{stop['id']:<6}  {stop['name']}"


def _normalize_payload(raw: Any) -> list[dict[str, Any]]:
    items = raw if isinstance(raw, list) else (raw.get("stops") if isinstance(raw, dict) else None) or []
    out: list[dict[str, Any]] = []
    for it in items:
        sid = it.get("stopId") or it.get("stop_id") or it.get("id")
        name = it.get("stopName") or it.get("stop_name") or it.get("name")
        if isinstance(sid, int) and isinstance(name, str):
            out.append({"id": sid, "name": name})
    return sorted(out, key=lambda s: s["name"])


async def _amain(query: str | None, show_all: bool) -> int:
    async with ClientSession() as session:
        client = ZTMGdanskClient(session)
        raw = await client.get_stops()
    stops = _normalize_payload(raw)
    if show_all:
        results = stops
    elif query:
        results = filter_stops(stops, query)
    else:
        print("Pass a query, or use --all", file=sys.stderr)
        return 2
    for s in results:
        print(format_row(s))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Find ZTM Gdańsk stop IDs")
    p.add_argument("query", nargs="?", help="Substring to match (case/diacritics insensitive)")
    p.add_argument("--all", action="store_true", help="Print all stops")
    args = p.parse_args()
    return asyncio.run(_amain(args.query, args.all))


if __name__ == "__main__":
    raise SystemExit(main())
