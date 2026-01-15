import argparse
import os
import sys

from ilp_utils import (
    fmt_float,
    get_irrigation_levels,
    get_soil_types,
    load_config,
    read_csv_rows,
    wpf_yield_t_ha,
    write_csv_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ds_table.csv from cell_table.csv")
    parser.add_argument("--input", default="cell_table.csv", help="Input cell table CSV")
    parser.add_argument("--output", default="ds_table.csv", help="Output DS table CSV")
    parser.add_argument("--config", default="ilp_config.json", help="Config JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    soil_types = get_soil_types(cfg)
    levels = get_irrigation_levels(cfg)
    price = float(cfg.get("price_per_t", 0.0))
    water_cost = float(cfg.get("water_cost_per_mm_ha", 0.0))

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    ds_cells = {j: [] for j in range(360)}
    ds_area = {j: 0.0 for j in range(360)}

    for row in read_csv_rows(args.input):
        ds_id = int(float(row["ds_id"]))
        area_m2 = float(row["area_m2"]) if "area_m2" in row else float(row["Shape_Area"])
        soil_type = row.get("soil_type", "").strip()

        if "wpf_ymin" in row and "wpf_ymax" in row and "wpf_k" in row:
            y_min = float(row["wpf_ymin"])
            y_max = float(row["wpf_ymax"])
            k_param = float(row["wpf_k"])
        else:
            if soil_type not in soil_types:
                raise ValueError(f"Unknown soil_type '{soil_type}' for ds_id {ds_id}")
            params = soil_types[soil_type]
            y_min = float(params["y_min"])
            y_max = float(params["y_max"])
            k_param = float(params["k"])

        ds_cells[ds_id].append((area_m2, y_min, y_max, k_param))
        ds_area[ds_id] += area_m2

    rows_out = []
    for ds_id in range(360):
        area_m2 = ds_area[ds_id]
        area_ha = area_m2 / 10000.0

        for iw_mm in levels:
            if area_m2 <= 0.0:
                y_avg = 0.0
            else:
                y_sum = 0.0
                for area_cell, y_min, y_max, k_param in ds_cells[ds_id]:
                    y_cell = wpf_yield_t_ha(y_min, y_max, k_param, iw_mm)
                    y_sum += y_cell * area_cell
                y_avg = y_sum / area_m2

            profit_rate = price * y_avg - water_cost * iw_mm
            profit_total = profit_rate * area_ha

            rows_out.append(
                {
                    "ds_id": str(ds_id),
                    "iw_mm": fmt_float(float(iw_mm), 2),
                    "area_m2": fmt_float(area_m2),
                    "area_ha": fmt_float(area_ha),
                    "yield_t_ha": fmt_float(y_avg),
                    "profit_rate_per_ha": fmt_float(profit_rate),
                    "profit_total": fmt_float(profit_total),
                }
            )

    out_fields = [
        "ds_id",
        "iw_mm",
        "area_m2",
        "area_ha",
        "yield_t_ha",
        "profit_rate_per_ha",
        "profit_total",
    ]
    write_csv_rows(args.output, out_fields, rows_out)
    print(f"Wrote {len(rows_out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
