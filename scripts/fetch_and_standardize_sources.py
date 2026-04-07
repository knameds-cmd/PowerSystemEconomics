from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


DATA_GO_SOURCES: Dict[str, Dict[str, Any]] = {
    "smp_forecast_demand": {
        "base_url": "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand",
        "raw_path": "data/raw/smp_forecast_demand",
        "csv_path": "data/processed/standardized/smp_forecast_demand.csv",
    },
    "power_market_gen_info": {
        "base_url": "https://apis.data.go.kr/B552115/PowerMarketGenInfo/getPowerMarketGenInfo",
        "raw_path": "data/raw/power_market_gen_info",
        "csv_path": "data/processed/standardized/power_market_gen_info.csv",
    },
    "fuel_cost": {
        "base_url": "https://apis.data.go.kr/B552115/FuelCost1/getFuelCost1",
        "raw_path": "data/raw/fuel_cost",
        "csv_path": "data/processed/standardized/fuel_cost.csv",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch approved sources and write standardized CSV files.")
    parser.add_argument(
        "--service-key",
        default=os.environ.get("DATA_GO_KR_SERVICE_KEY", ""),
        help="Decoded data.go.kr service key",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=1000,
        help="Rows per request for data.go.kr sources",
    )
    parser.add_argument(
        "--skip-data-go",
        action="store_true",
        help="Skip fresh downloads for data.go.kr sources and only build CSVs from existing raw files.",
    )
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_url(base_url: str, query: Dict[str, Any]) -> str:
    return f"{base_url}?{urlencode(query)}"


def fetch_json(base_url: str, query: Dict[str, Any]) -> Dict[str, Any]:
    url = build_url(base_url, query)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "PowerSystemEconomics/1.0"})

    attempts = 0
    while True:
        attempts += 1
        try:
            with urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8", errors="replace")
            return json.loads(body)["response"]
        except HTTPError as exc:
            if exc.code == 429 and attempts < 8:
                time.sleep(min(30, attempts * 5))
                continue
            raise


def get_items(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = response.get("body") or {}
    items = body.get("items") or {}
    item = items.get("item")
    if item is None:
        return []
    if isinstance(item, list):
        return item
    return [item]


def fetch_data_go_source(source_key: str, config: Dict[str, Any], service_key: str, page_size: int, root: Path) -> Path:
    if not service_key:
        raise RuntimeError("Missing DATA_GO_KR_SERVICE_KEY for approved data.go.kr downloads.")

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    snapshot_dir = root / config["raw_path"] / f"snapshot={timestamp}"
    ensure_dir(snapshot_dir)

    page_no = 1
    total_count = None
    pages: List[str] = []

    while True:
        print(f"[FETCH] {source_key} page={page_no}")
        query = {
            "serviceKey": service_key,
            "pageNo": page_no,
            "numOfRows": page_size,
            "dataType": "json",
        }
        response = fetch_json(config["base_url"], query)
        if response["header"]["resultCode"] != "00":
            raise RuntimeError(f"{source_key} returned {response['header']['resultCode']}: {response['header']['resultMsg']}")

        body = response.get("body") or {}
        if total_count is None:
            total_count = int(body.get("totalCount", 0))

        page_path = snapshot_dir / f"page-{page_no:04d}.json"
        write_json(page_path, response)
        pages.append(page_path.name)

        rows = get_items(response)
        if len(rows) < page_size:
            break

        page_no += 1

    manifest = {
        "source": source_key,
        "base_url": config["base_url"],
        "downloaded_at": timestamp,
        "page_size": page_size,
        "page_count": len(pages),
        "total_count": total_count,
        "pages": pages,
    }
    write_json(snapshot_dir / "manifest.json", manifest)
    return snapshot_dir


def latest_snapshot(path: Path) -> Path:
    snapshots = sorted([p for p in path.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not snapshots:
        raise RuntimeError(f"No snapshot directories found under {path}")
    return snapshots[-1]


def iter_page_payloads(snapshot_dir: Path) -> Iterable[Dict[str, Any]]:
    for page_path in sorted(snapshot_dir.glob("page-*.json")):
        yield read_json(page_path)


def collect_rows_from_snapshot(snapshot_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for payload in iter_page_payloads(snapshot_dir):
        rows.extend(get_items(payload))
    return rows


def normalize_smp_forecast(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "date": "trade_date",
            "hour": "hour",
            "areaName": "market_area",
            "smp": "smp",
            "mlfd": "mainland_load_forecast_mw",
            "jlfd": "jeju_load_forecast_mw",
            "slfd": "system_load_forecast_mw",
            "rn": "row_number",
        }
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    for column in ("hour", "row_number"):
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    for column in ("smp", "mainland_load_forecast_mw", "jeju_load_forecast_mw", "system_load_forecast_mw"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df[
        [
            "trade_date",
            "hour",
            "market_area",
            "smp",
            "system_load_forecast_mw",
            "mainland_load_forecast_mw",
            "jeju_load_forecast_mw",
            "row_number",
        ]
    ]
    return df.sort_values(["trade_date", "hour", "market_area"]).reset_index(drop=True)


def normalize_power_market(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "area": "market_area",
            "company": "company_name",
            "cent": "dispatch_type",
            "genNm": "generator_name",
            "genSrc": "generation_source",
            "genFom": "generation_form",
            "fuel": "fuel_type",
            "pcap": "capacity_mw",
            "rn": "row_number",
        }
    )
    df["capacity_mw"] = pd.to_numeric(df["capacity_mw"], errors="coerce")
    df["row_number"] = pd.to_numeric(df["row_number"], errors="coerce").astype("Int64")
    df = df[
        [
            "row_number",
            "market_area",
            "company_name",
            "generator_name",
            "dispatch_type",
            "generation_source",
            "generation_form",
            "fuel_type",
            "capacity_mw",
        ]
    ]
    return df.sort_values(["row_number"]).reset_index(drop=True)


def normalize_fuel_cost(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "day": "year_month",
            "fuelType": "fuel_type",
            "untpcType": "unit_price_type",
            "untpc": "unit_price",
            "unit": "unit",
            "rn": "row_number",
        }
    )
    df["year_month"] = pd.to_datetime(df["year_month"], format="%Y%m").dt.strftime("%Y-%m")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["row_number"] = pd.to_numeric(df["row_number"], errors="coerce").astype("Int64")
    df = df[
        [
            "year_month",
            "fuel_type",
            "unit_price_type",
            "unit_price",
            "unit",
            "row_number",
        ]
    ]
    return df.sort_values(["year_month", "fuel_type", "unit_price_type"]).reset_index(drop=True)


def normalize_renewables(snapshot_dir: Path) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for payload in iter_page_payloads(snapshot_dir):
        rows.extend(payload.get("data") or [])

    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "거래일자": "trade_date",
            "거래시간": "hour",
            "연료원": "fuel_type",
            "전력거래량(MWh)": "generation_mwh",
            "지역": "region",
        }
    )
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").astype("Int64")
    df["generation_mwh"] = pd.to_numeric(df["generation_mwh"], errors="coerce")
    df = df[["trade_date", "hour", "region", "fuel_type", "generation_mwh"]]
    return df.sort_values(["trade_date", "hour", "region", "fuel_type"]).reset_index(drop=True)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> int:
    args = parse_args()
    root = repo_root()

    if not args.skip_data_go:
        for source_key, config in DATA_GO_SOURCES.items():
            snapshot_dir = fetch_data_go_source(
                source_key=source_key,
                config=config,
                service_key=args.service_key,
                page_size=args.page_size,
                root=root,
            )
            rows = collect_rows_from_snapshot(snapshot_dir)
            if source_key == "smp_forecast_demand":
                df = normalize_smp_forecast(rows)
            elif source_key == "power_market_gen_info":
                df = normalize_power_market(rows)
            elif source_key == "fuel_cost":
                df = normalize_fuel_cost(rows)
            else:
                raise RuntimeError(f"Unhandled source: {source_key}")

            write_csv(df, root / config["csv_path"])
            print(f"[OK] {source_key}: {len(df)} rows -> {root / config['csv_path']}")

    renewables_snapshot = latest_snapshot(root / "data/raw/renewables")
    renewables_df = normalize_renewables(renewables_snapshot)
    renewables_csv = root / "data/processed/standardized/regional_renewables.csv"
    write_csv(renewables_df, renewables_csv)
    print(f"[OK] regional_renewables: {len(renewables_df)} rows -> {renewables_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
