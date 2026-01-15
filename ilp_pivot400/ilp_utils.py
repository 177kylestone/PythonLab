import csv
import json
import math
from typing import Dict, Iterable, List, Tuple


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_pivot_center(cfg: dict) -> Tuple[float, float]:
    center = cfg.get("pivot_center", {})
    return float(center["x"]), float(center["y"])


def get_irrigation_levels(cfg: dict) -> List[float]:
    levels = cfg.get("irrigation_levels_mm", [])
    if not levels:
        raise ValueError("irrigation_levels_mm is missing or empty in config")
    return [float(v) for v in levels]


def get_soil_types(cfg: dict) -> Dict[str, dict]:
    soil_types = cfg.get("soil_types", {})
    if not soil_types:
        raise ValueError("soil_types is missing or empty in config")
    return soil_types


def compute_bearing_deg(dx: float, dy: float) -> float:
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    if bearing >= 360.0:
        return 0.0
    return bearing


def ds_id_from_bearing(bearing: float) -> int:
    ds = int(math.floor(bearing))
    if ds < 0:
        return 0
    if ds > 359:
        return 359
    return ds


def wpf_yield_t_ha(y_min: float, y_max: float, k_param: float, iw_mm: float) -> float:
    if iw_mm <= 0.0:
        return y_min
    return y_min + (y_max - y_min) * (1.0 - math.exp(-k_param * iw_mm))


def read_csv_rows(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def write_csv_rows(path: str, fieldnames: List[str], rows: Iterable[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt_float(value: float, ndigits: int = 6) -> str:
    return f"{value:.{ndigits}f}"
