import argparse
import csv
import os
import sys

from ilp_utils import (
    compute_bearing_deg,
    ds_id_from_bearing,
    fmt_float,
    get_pivot_center,
    get_soil_types,
    load_config,
    read_csv_rows,
    write_csv_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cell_table.csv from Pivot_400m_Table.csv")
    parser.add_argument("--input", default="Pivot_400m_Table.csv", help="Input ArcGIS CSV")
    parser.add_argument("--output", default="cell_table.csv", help="Output cell table CSV")
    parser.add_argument("--config", default="ilp_config.json", help="Config JSON path")
    parser.add_argument(
        "--soil-map",
        default="",
        help="Optional CSV with OBJECTID,soil_type columns",
    )
    parser.add_argument(
        "--assign-by-bearing",
        action="store_true",
        help="Assign soil types by bearing wedges when no soil map or soil_type column exists",
    )
    return parser.parse_args()


def load_soil_map(path: str) -> dict:
    soil_map = {}
    if not path:
        return soil_map
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "OBJECTID" not in row or "soil_type" not in row:
                raise ValueError("soil map must include OBJECTID and soil_type columns")
            soil_map[str(row["OBJECTID"]).strip()] = str(row["soil_type"]).strip()
    return soil_map


def pick_field(fieldnames, candidates):
    for name in candidates:
        if name in fieldnames:
            return name
    return None


def assign_soil_by_bearing(bearing: float, soil_names):
    n = len(soil_names)
    if n == 0:
        return ""
    wedge = 360.0 / n
    idx = int(bearing // wedge)
    if idx >= n:
        idx = n - 1
    return soil_names[idx]


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    center_x, center_y = get_pivot_center(cfg)
    soil_types = get_soil_types(cfg)
    soil_names = list(soil_types.keys())
    default_soil = cfg.get("default_soil_type", soil_names[0] if soil_names else "")
    soil_map = load_soil_map(args.soil_map)

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    rows_out = []
    fieldnames = None
    for row in read_csv_rows(args.input):
        if fieldnames is None:
            fieldnames = list(row.keys())

        x_field = pick_field(fieldnames, ["centroid_x", "POINT_X", "x", "X"])
        y_field = pick_field(fieldnames, ["centroid_y", "POINT_Y", "y", "Y"])
        if not x_field or not y_field:
            raise ValueError("Missing centroid_x/centroid_y (or POINT_X/POINT_Y) columns")

        area_field = pick_field(fieldnames, ["Shape_Area", "shape_area", "AREA", "area"])
        if not area_field:
            raise ValueError("Missing Shape_Area column")

        object_id = str(row.get("OBJECTID", "")).strip()
        centroid_x = float(row[x_field])
        centroid_y = float(row[y_field])
        area_m2 = float(row[area_field])

        dx = centroid_x - center_x
        dy = centroid_y - center_y
        bearing = compute_bearing_deg(dx, dy)
        ds_id = ds_id_from_bearing(bearing)

        soil_type = ""
        if "soil_type" in row and str(row["soil_type"]).strip():
            soil_type = str(row["soil_type"]).strip()
        elif object_id in soil_map:
            soil_type = soil_map[object_id]
        elif args.assign_by_bearing:
            soil_type = assign_soil_by_bearing(bearing, soil_names)
        else:
            soil_type = default_soil

        if soil_type not in soil_types:
            raise ValueError(f"Unknown soil_type '{soil_type}' for OBJECTID {object_id}")

        params = soil_types[soil_type]
        out_row = {
            "cell_id": object_id,
            "centroid_x": fmt_float(centroid_x),
            "centroid_y": fmt_float(centroid_y),
            "dx": fmt_float(dx),
            "dy": fmt_float(dy),
            "bearing_deg": fmt_float(bearing),
            "ds_id": str(ds_id),
            "area_m2": fmt_float(area_m2),
            "soil_type": soil_type,
            "wpf_ymin": fmt_float(float(params["y_min"])),
            "wpf_ymax": fmt_float(float(params["y_max"])),
            "wpf_k": fmt_float(float(params["k"])),
        }
        rows_out.append(out_row)

    out_fields = [
        "cell_id",
        "centroid_x",
        "centroid_y",
        "dx",
        "dy",
        "bearing_deg",
        "ds_id",
        "area_m2",
        "soil_type",
        "wpf_ymin",
        "wpf_ymax",
        "wpf_k",
    ]
    write_csv_rows(args.output, out_fields, rows_out)
    print(f"Wrote {len(rows_out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
