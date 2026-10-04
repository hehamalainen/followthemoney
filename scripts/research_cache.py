"""Portable caches and guarded writes for the fixed research snapshot (stdlib only)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def cache_path(kind: str, supplied: Path | None = None, site: Path = ROOT) -> Path:
    """CLI path wins, then environment, then the checkout-local cache."""
    env = {"sec": "AI_MONEY_MAP_SEC_CACHE", "prices": "AI_MONEY_MAP_PRICE_CACHE"}[kind]
    return Path(supplied or os.environ.get(env) or site / ".cache" / kind).expanduser().resolve()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc


def atomic_write(path: Path, contents: str) -> None:
    """Replace only after the entire new file was successfully written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name+".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def snapshot_ciks(site: Path = ROOT) -> dict[str, int]:
    rows = read_json(site / "dist" / "data.json")["companies"]
    result = {row["ticker"]: int(row["cik"]) for row in rows if row.get("cik")}
    if not result:
        raise ValueError("Saved snapshot has no SEC identifiers; refusing to infer an empty cache requirement.")
    return result


def validate_facts(data: Any, ticker: str, cik: int) -> None:
    if not isinstance(data, dict) or str(data.get("cik", "")).lstrip("0") != str(cik):
        raise ValueError(f"{ticker}: SEC cache CIK does not match the saved issuer ({cik}).")
    facts = data.get("facts")
    if not isinstance(facts, dict) or not any(isinstance(facts.get(ns), dict) and facts[ns]
                                              for ns in ("us-gaap", "ifrs-full")):
        raise ValueError(f"{ticker}: SEC cache has no standard financial facts.")


def require_sec_cache(cache: Path, site: Path = ROOT) -> dict[str, int]:
    """A public checkout cannot silently replace known SEC coverage with nulls."""
    required = snapshot_ciks(site)
    problems = []
    for ticker, cik in required.items():
        path = cache / (ticker + ".json")
        if not path.is_file():
            problems.append(ticker + " (missing)")
            continue
        try:
            validate_facts(read_json(path), ticker, cik)
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        sample = "; ".join(problems[:12])
        more = f"; and {len(problems)-12} more" if len(problems)>12 else ""
        raise ValueError(f"SEC cache is absent or incomplete at {cache}: {sample}{more}. "
                         "Saved outputs were not changed. Populate it with fetch_financials.py --cache PATH "
                         "(SEC_USER_AGENT required for network), or point --cache / AI_MONEY_MAP_SEC_CACHE "
                         "at a complete existing cache.")
    return required


def sec_user_agent() -> str:
    agent = os.environ.get("SEC_USER_AGENT", "").strip()
    match = re.search(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", agent)
    domain = match.group(1).lower() if match else ""
    reserved = domain in {"example.com", "example.org", "example.net"} or domain.endswith((".example", ".invalid", ".test"))
    if not match or reserved or "\n" in agent or "\r" in agent:
        raise ValueError("Set SEC_USER_AGENT to an application name plus your real contact email before "
                         "SEC network access. Placeholder/example addresses are not accepted. "
                         "Existing valid cached files can be used without this setting.")
    return agent
