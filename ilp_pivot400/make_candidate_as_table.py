import argparse
import os
import sys

from ilp_utils import fmt_float, get_irrigation_levels, load_config, read_csv_rows, write_csv_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate_as_table.csv from ds_table.csv")
    parser.add_argument("--input", default="ds_table.csv", help="Input DS table CSV")
    parser.add_argument("--output", default="candidate_as_table.csv", help="Output candidate AS table CSV")
    parser.add_argument("--config", default="ilp_config.json", help="Config JSON path")
    return parser.parse_args()


def build_prefix(values):
    arr = values + values
    prefix = [0.0]
    for v in arr:
        prefix.append(prefix[-1] + v)
    return prefix


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    levels = get_irrigation_levels(cfg)
    arc_cfg = cfg.get("arc_sectors", {})
    lmin = int(arc_cfg.get("lmin_deg", 5))
    lmax = int(arc_cfg.get("lmax_deg", 120))
    include_full = bool(arc_cfg.get("include_full_circle", True))

    if not os.path.exists(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    profits = {float(iw): [0.0 for _ in range(360)] for iw in levels}
    area_by_ds = [0.0 for _ in range(360)]

    for row in read_csv_rows(args.input):
        ds_id = int(float(row["ds_id"]))
        iw_mm = float(row["iw_mm"])
        profit_total = float(row["profit_total"])
        area_m2 = float(row["area_m2"])

        if iw_mm not in profits:
            profits[iw_mm] = [0.0 for _ in range(360)]
        profits[iw_mm][ds_id] = profit_total
        if area_by_ds[ds_id] == 0.0:
            area_by_ds[ds_id] = area_m2

    area_prefix = build_prefix(area_by_ds)
    profit_prefix = {iw: build_prefix(profits[iw]) for iw in profits}

    rows_out = []
    as_id = 0
    for start in range(360):
        for length in range(lmin, lmax + 1):
            if length >= 360:
                continue
            as_id += 1
            area_m2 = area_prefix[start + length] - area_prefix[start]
            for iw_mm in levels:
                profit_sum = profit_prefix[iw_mm][start + length] - profit_prefix[iw_mm][start]
                water_m3 = (iw_mm * area_m2) / 1000.0
                rows_out.append(
                    {
                        "as_id": str(as_id),
                        "start_deg": str(start),
                        "length_deg": str(length),
                        "iw_mm": fmt_float(iw_mm, 2),
                        "area_m2": fmt_float(area_m2),
                        "water_m3": fmt_float(water_m3),
                        "profit_total": fmt_float(profit_sum),
                        "full_circle": "0",
                    }
                )

    if include_full:
        as_id += 1
        start = 0
        length = 360
        area_m2 = area_prefix[start + length] - area_prefix[start]
        for iw_mm in levels:
            profit_sum = profit_prefix[iw_mm][start + length] - profit_prefix[iw_mm][start]
            water_m3 = (iw_mm * area_m2) / 1000.0
            rows_out.append(
                {
                    "as_id": str(as_id),
                    "start_deg": str(start),
                    "length_deg": str(length),
                    "iw_mm": fmt_float(iw_mm, 2),
                    "area_m2": fmt_float(area_m2),
                    "water_m3": fmt_float(water_m3),
                    "profit_total": fmt_float(profit_sum),
                    "full_circle": "1",
                }
            )

    out_fields = [
        "as_id",
        "start_deg",
        "length_deg",
        "iw_mm",
        "area_m2",
        "water_m3",
        "profit_total",
        "full_circle",
    ]
    write_csv_rows(args.output, out_fields, rows_out)
    print(f"Wrote {len(rows_out)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
