from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import yaml

from app.core.database import async_session
from app.services.curation.trend_candidate_selector import TrendCandidateSelector


DEFAULT_TIER_CONFIG = (
    Path(__file__).resolve().parents[2] / "crawl_targets" / "source_tiers.yaml"
)


def _load_tier_config(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Tier config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Tier config must be a YAML object")
    return data


async def _run(args: argparse.Namespace) -> None:
    tier_config_path = Path(args.tier_config) if args.tier_config else None
    tier_config = _load_tier_config(tier_config_path) if tier_config_path else {}

    async with async_session() as session:
        selector = TrendCandidateSelector(session, tier_config=tier_config)
        result = await selector.select_candidates(
            hours=args.hours,
            similarity_threshold=args.similarity_threshold,
            max_candidates=args.max_candidates,
            limit=args.limit,
            ensure_vector_table=not args.no_ensure_vector_table,
        )

    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=True))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select trend candidates from crawled contents "
        "(time window + semantic dedup + source tiering)."
    )
    parser.add_argument("--hours", type=int, default=12, help="Lookback window in hours.")
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Cosine similarity threshold for semantic dedup (0~1).",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=200,
        help="Maximum number of recent records to evaluate before dedup.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Final number of candidates after dedup and tier sorting.",
    )
    parser.add_argument(
        "--tier-config",
        default=str(DEFAULT_TIER_CONFIG),
        help="Path to YAML source tier config.",
    )
    parser.add_argument(
        "--out-json",
        default="",
        help="Optional output JSON file path.",
    )
    parser.add_argument(
        "--no-ensure-vector-table",
        action="store_true",
        help="Skip automatic pgvector table bootstrap.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
