import json
import os
import tempfile

import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "cleaned_wildfire_data_2024.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Cleaned wildfire CSV must exist in S3 before compute_statistics can run")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "wildfire_statistics_2024.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Aggregated wildfire statistics JSON must be present in S3 after compute_statistics completes")
        raise SystemExit(1)
# --- end contract helpers ---


def compute_statistics(folder: str, input1: str, output1: str) -> None:
    """
    Read the cleaned 2024 California wildfire dataset from S3.
    Compute and aggregate summary statistics:
      1. Total acres burned grouped by month
      2. Top 10 fires ranked by size in acres
      3. Number of fires per county
      4. Seasonal trends (Winter=Dec-Feb, Spring=Mar-May, Summer=Jun-Aug,
         Fall=Sep-Nov) with total acres and fire counts per season
    Write all computed statistics as a structured JSON file to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log(
        f"compute_statistics: downloading {input1} from folder '{folder}'"
    )

    tmp_input = None
    tmp_output = None

    try:
        # ------------------------------------------------------------------
        # 1. Download cleaned CSV from S3 into a temp file
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_in:
            tmp_input = tmp_in.name

        faasr_get_file(
            local_file=tmp_input,
            remote_folder=folder,
            remote_file=input1,
        )

        faasr_log(
            f"compute_statistics: reading {input1} from local temp file"
        )

        # ------------------------------------------------------------------
        # 2. Load CSV — fail loudly if it is empty or unreadable
        # ------------------------------------------------------------------
        try:
            df = pd.read_csv(tmp_input)
        except Exception as exc:
            faasr_log(
                f"compute_statistics: failed to parse {input1} as CSV: {exc}"
            )
            raise RuntimeError(
                f"Cannot parse {input1} as CSV: {exc}"
            ) from exc

        if df.empty:
            faasr_log(
                f"compute_statistics: {input1} loaded 0 rows — "
                "upstream clean_and_filter_data must have returned no data. "
                "Do NOT fabricate data."
            )
            raise RuntimeError(
                f"{input1} is empty. Cannot compute statistics without real "
                "wildfire data."
            )

        faasr_log(
            f"compute_statistics: loaded {len(df)} rows, "
            f"columns: {list(df.columns)}"
        )

        # ------------------------------------------------------------------
        # 3. Ensure required columns exist; fail loudly if critical ones
        #    are absent.
        # ------------------------------------------------------------------
        required_cols = {"start_date", "acres_burned"}
        missing = required_cols - set(df.columns)
        if missing:
            faasr_log(
                f"compute_statistics: required columns missing from "
                f"{input1}: {sorted(missing)}"
            )
            raise RuntimeError(
                f"Cannot compute statistics — missing columns: "
                f"{sorted(missing)}"
            )

        # ------------------------------------------------------------------
        # 4. Parse dates and derive month / season helper columns
        # ------------------------------------------------------------------
        df["start_date_dt"] = pd.to_datetime(df["start_date"], errors="coerce")
        df["month"] = df["start_date_dt"].dt.month          # 1–12 (NaN if unparseable)
        df["month_name"] = df["start_date_dt"].dt.strftime("%B")  # 'January', …
        df["year_month"] = df["start_date_dt"].dt.strftime("%Y-%m")  # '2024-01'

        def _month_to_season(m):
            """Map month number (1–12) to season name."""
            if pd.isna(m):
                return None
            m = int(m)
            if m in (12, 1, 2):
                return "Winter"
            elif m in (3, 4, 5):
                return "Spring"
            elif m in (6, 7, 8):
                return "Summer"
            elif m in (9, 10, 11):
                return "Fall"
            return None

        df["season"] = df["month"].apply(_month_to_season)

        # Coerce acres_burned to numeric (upstream already does this, but
        # be defensive)
        df["acres_burned"] = pd.to_numeric(df["acres_burned"], errors="coerce")

        # ------------------------------------------------------------------
        # 5. Statistic 1 — Total acres burned grouped by month
        #    Only include rows with a valid date and non-NaN acreage.
        # ------------------------------------------------------------------
        monthly_df = (
            df.dropna(subset=["year_month", "acres_burned"])
            .groupby("year_month", sort=True)["acres_burned"]
            .agg(total_acres="sum", fire_count="count")
            .reset_index()
        )

        monthly_acres = [
            {
                "month": row["year_month"],
                "total_acres_burned": round(float(row["total_acres"]), 2),
                "fire_count": int(row["fire_count"]),
            }
            for _, row in monthly_df.iterrows()
        ]

        faasr_log(
            f"compute_statistics: computed monthly stats for "
            f"{len(monthly_acres)} months"
        )

        # ------------------------------------------------------------------
        # 6. Statistic 2 — Top 10 fires ranked by size in acres
        # ------------------------------------------------------------------
        top10_df = (
            df.dropna(subset=["acres_burned"])
            .nlargest(10, "acres_burned")
            .reset_index(drop=True)
        )

        top10_fires = []
        for rank_idx, row in top10_df.iterrows():
            entry = {
                "rank": rank_idx + 1,
                "fire_name": (
                    str(row["fire_name"])
                    if "fire_name" in df.columns and pd.notna(row.get("fire_name"))
                    else None
                ),
                "acres_burned": round(float(row["acres_burned"]), 2),
                "start_date": (
                    str(row["start_date"])
                    if "start_date" in df.columns and pd.notna(row.get("start_date"))
                    else None
                ),
                "county": (
                    str(row["county"])
                    if "county" in df.columns and pd.notna(row.get("county"))
                    else None
                ),
                "latitude": (
                    round(float(row["latitude"]), 6)
                    if "latitude" in df.columns and pd.notna(row.get("latitude"))
                    else None
                ),
                "longitude": (
                    round(float(row["longitude"]), 6)
                    if "longitude" in df.columns and pd.notna(row.get("longitude"))
                    else None
                ),
            }
            top10_fires.append(entry)

        faasr_log(
            f"compute_statistics: identified top {len(top10_fires)} fires by "
            "acres burned"
        )

        # ------------------------------------------------------------------
        # 7. Statistic 3 — Number of fires per county
        # ------------------------------------------------------------------
        if "county" in df.columns:
            county_df = (
                df.dropna(subset=["county"])
                .groupby("county", sort=True)
                .agg(
                    fire_count=("county", "count"),
                    total_acres_burned=("acres_burned", "sum"),
                )
                .reset_index()
            )
            fires_per_county = [
                {
                    "county": str(row["county"]),
                    "fire_count": int(row["fire_count"]),
                    "total_acres_burned": round(float(row["total_acres_burned"]), 2),
                }
                for _, row in county_df.iterrows()
            ]
        else:
            faasr_log(
                "compute_statistics: 'county' column not present — "
                "fires_per_county will be empty"
            )
            fires_per_county = []

        faasr_log(
            f"compute_statistics: computed fire counts for "
            f"{len(fires_per_county)} counties"
        )

        # ------------------------------------------------------------------
        # 8. Statistic 4 — Seasonal trends
        #    Season order: Winter, Spring, Summer, Fall
        # ------------------------------------------------------------------
        season_order = ["Winter", "Spring", "Summer", "Fall"]

        seasonal_df = (
            df.dropna(subset=["season", "acres_burned"])
            .groupby("season", sort=False)
            .agg(
                total_acres_burned=("acres_burned", "sum"),
                fire_count=("season", "count"),
            )
            .reset_index()
        )

        # Build a dict for easy lookup, then output in canonical season order
        seasonal_lookup = {
            row["season"]: {
                "season": row["season"],
                "total_acres_burned": round(float(row["total_acres_burned"]), 2),
                "fire_count": int(row["fire_count"]),
            }
            for _, row in seasonal_df.iterrows()
        }

        seasonal_trends = []
        for season_name in season_order:
            if season_name in seasonal_lookup:
                seasonal_trends.append(seasonal_lookup[season_name])
            else:
                # Season with no fires still deserves an entry
                seasonal_trends.append(
                    {
                        "season": season_name,
                        "total_acres_burned": 0.0,
                        "fire_count": 0,
                    }
                )

        faasr_log("compute_statistics: computed seasonal trend statistics")

        # ------------------------------------------------------------------
        # 9. Assemble final statistics dict
        # ------------------------------------------------------------------
        statistics = {
            "summary": {
                "total_fires": int(len(df)),
                "total_acres_burned": round(
                    float(df["acres_burned"].sum(skipna=True)), 2
                ),
                "data_year": 2024,
                "state": "California (US-CA)",
            },
            "monthly_acres_burned": monthly_acres,
            "top_10_fires_by_size": top10_fires,
            "fires_per_county": fires_per_county,
            "seasonal_trends": seasonal_trends,
        }

        # ------------------------------------------------------------------
        # 10. Write JSON to a temp file, then upload to S3
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_out:
            tmp_output = tmp_out.name

        with open(tmp_output, "w", encoding="utf-8") as fh:
            json.dump(statistics, fh, indent=2, default=str)

        faasr_log(
            f"compute_statistics: uploading {output1} to folder '{folder}'"
        )
        faasr_put_file(
            local_file=tmp_output,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log(
            f"compute_statistics: successfully uploaded {output1} "
            f"to S3 folder '{folder}'"
        )

    finally:
        if tmp_input and os.path.exists(tmp_input):
            os.remove(tmp_input)
        if tmp_output and os.path.exists(tmp_output):
            os.remove(tmp_output)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---