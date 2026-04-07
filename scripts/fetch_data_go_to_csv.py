from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


SOURCES: Dict[str, Dict[str, Any]] = {
    "smp_forecast_demand": {
        "base_url": "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand",
        "params": {},
    },
    "power_market_gen_info": {
        "base_url": "https://apis.data.go.kr/B552115/PowerMarketGenInfo/getPowerMarketGenInfo",
        "params": {},
    },
    "fuel_cost": {
        "base_url": "https://apis.data.go.kr/B552115/FuelCost1/getFuelCost1",
        "params": {},
    },
    "smp_decision_by_fuel": {
        "base_url": "https://apis.data.go.kr/B552115/SmpDecByFuel2/getSmpDecByFuel2",
        "params": {},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Try data.go.kr KPX endpoints and save CSV outputs when successful.")
    parser.add_argument(
        "--source",
        nargs="+",
        default=list(SOURCES.keys()),
        choices=list(SOURCES.keys()),
        help="One or more source keys to fetch.",
    )
    parser.add_argument("--service-key", default=os.environ.get("DATA_GO_KR_SERVICE_KEY", ""), help="Decoded service key.")
    parser.add_argument("--page-size", type=int, default=100, help="Rows per page.")
    parser.add_argument("--max-pages", type=int, default=2, help="Maximum pages to fetch per source for trial.")
    parser.add_argument(
        "--output-dir",
        default="data/processed/python_trials",
        help="Directory for trial CSV and metadata files.",
    )
    return parser.parse_args()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fetch_json(base_url: str, query: Dict[str, Any]) -> Tuple[int, str, Dict[str, Any] | None]:
    url = f"{base_url}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "PowerSystemEconomics/1.0",
        },
    )

    try:
        with urlopen(request, timeout=60) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
            return status, body, json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, None
    except URLError as exc:
        return 0, str(exc), None


def normalize_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = payload.get("body") or {}
    items = body.get("items") or {}
    item = items.get("item")
    if item is None:
        return []
    if isinstance(item, list):
        return item
    return [item]


def save_metadata(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_source(source_key: str, config: Dict[str, Any], service_key: str, page_size: int, max_pages: int, output_root: Path) -> None:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    source_dir = output_root / source_key / f"trial={timestamp}"
    source_dir.mkdir(parents=True, exist_ok=True)

    all_rows: List[Dict[str, Any]] = []
    pages: List[Dict[str, Any]] = []

    for page_no in range(1, max_pages + 1):
        query = {
            "serviceKey": service_key,
            "pageNo": page_no,
            "numOfRows": page_size,
            "dataType": "json",
        }
        query.update(config.get("params", {}))

        status_code, body, payload = fetch_json(config["base_url"], query)
        page_meta = {
            "page_no": page_no,
            "status_code": status_code,
            "body_preview": body[:1000],
        }
        pages.append(page_meta)

        if payload is None:
            break

        rows = normalize_items(payload)
        all_rows.extend(rows)

        if len(rows) < page_size:
            break

    metadata = {
        "source": source_key,
        "downloaded_at": timestamp,
        "base_url": config["base_url"],
        "page_size": page_size,
        "max_pages": max_pages,
        "rows_collected": len(all_rows),
        "pages": pages,
    }
    save_metadata(source_dir / "metadata.json", metadata)

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(source_dir / "data.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] {source_key}: saved {len(df)} rows to {source_dir / 'data.csv'}")
    else:
        print(f"[FAIL] {source_key}: no rows saved. See {source_dir / 'metadata.json'}")


def main() -> int:
    args = parse_args()

    if not args.service_key:
        print("Missing service key. Pass --service-key or set DATA_GO_KR_SERVICE_KEY.", file=sys.stderr)
        return 1

    repo_root = get_repo_root()
    output_root = repo_root / args.output_dir
    output_root.mkdir(parents=True, exist_ok=True)

    for source_key in args.source:
        run_source(
            source_key=source_key,
            config=SOURCES[source_key],
            service_key=args.service_key,
            page_size=args.page_size,
            max_pages=args.max_pages,
            output_root=output_root,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
