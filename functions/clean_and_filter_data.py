import os
import tempfile

import pandas as pd


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "raw_wildfire_data_2024.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Raw wildfire data CSV must be present in S3 before cleaning can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "cleaned_wildfire_data_2024.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Cleaned wildfire data CSV must be uploaded to S3 after successful filtering and cleaning")
        raise SystemExit(1)
# --- end contract helpers ---


def clean_and_filter_data(folder: str, input1: str, output1: str) -> None:
    """
    Read the raw wildfire dataset CSV from S3, clean and filter it to 2024
    California wildfire events, and standardize key fields.

    The upstream fetch_wildfire_data function already queries NIFC WFIGS with
    a California (US-CA) and 2024 date filter, so the raw CSV should only
    contain CA 2024 records.  This function applies a defensive re-filter,
    coerces numeric fields, parses dates, and drops rows that are missing
    critical location data (latitude and/or longitude).
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log(
        f"clean_and_filter_data: downloading {input1} from folder '{folder}'"
    )

    tmp_input = None
    tmp_output = None

    try:
        # ------------------------------------------------------------------
        # 1. Download raw CSV from S3 into a temp file
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

        faasr_log(f"clean_and_filter_data: reading {input1} from local temp file")

        # ------------------------------------------------------------------
        # 2. Load CSV — fail loudly if it is empty or unreadable
        # ------------------------------------------------------------------
        try:
            df = pd.read_csv(tmp_input)
        except Exception as exc:
            faasr_log(
                f"clean_and_filter_data: failed to parse {input1} as CSV: {exc}"
            )
            raise RuntimeError(
                f"Cannot parse {input1} as CSV: {exc}"
            ) from exc

        if df.empty:
            faasr_log(
                f"clean_and_filter_data: {input1} loaded 0 rows — "
                "upstream fetch_wildfire_data must have returned no data. "
                "Do NOT fabricate data."
            )
            raise RuntimeError(
                f"{input1} is empty. Cannot proceed without real wildfire data."
            )

        faasr_log(
            f"clean_and_filter_data: loaded {len(df)} rows, "
            f"columns: {list(df.columns)}"
        )

        # ------------------------------------------------------------------
        # 3. Rename 'incident_name' → 'fire_name' for standardized output
        # ------------------------------------------------------------------
        if "incident_name" in df.columns:
            df = df.rename(columns={"incident_name": "fire_name"})

        # Strip leading/trailing whitespace from the fire name
        if "fire_name" in df.columns:
            df["fire_name"] = df["fire_name"].astype(str).str.strip()
            # Replace literal 'nan' strings (from None → str) with actual NaN
            df["fire_name"] = df["fire_name"].replace("nan", pd.NA)

        # ------------------------------------------------------------------
        # 3.5 Filter incident types: retain only actual wildfire records
        #     The upstream fetch_wildfire_data already filters for "WF", but
        #     we defensively re-apply here per the cleaning spec so that any
        #     stale or mixed CSV is also handled correctly.
        # ------------------------------------------------------------------
        if "incident_type" in df.columns:
            pre_type_count = len(df)
            df = df[df["incident_type"] == "WF"]
            excluded = pre_type_count - len(df)
            if excluded:
                faasr_log(
                    f"clean_and_filter_data: excluded {excluded} non-wildfire "
                    "rows (incident_type != 'WF' — prescribed burns, complexes, etc.)"
                )

        # ------------------------------------------------------------------
        # 4. Coerce numeric columns — invalid values become NaN
        # ------------------------------------------------------------------
        for col in ("acres_burned", "percent_contained", "latitude", "longitude"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Clamp percent_contained to [0, 100]
        if "percent_contained" in df.columns:
            df["percent_contained"] = df["percent_contained"].clip(lower=0, upper=100)

        # ------------------------------------------------------------------
        # 5. Parse start_date as a proper datetime; retain as ISO date string
        #    The upstream function writes ISO date strings (YYYY-MM-DD) but we
        #    parse with pandas to validate and re-format consistently.
        # ------------------------------------------------------------------
        if "start_date" in df.columns:
            df["start_date"] = pd.to_datetime(
                df["start_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        if "containment_date" in df.columns:
            df["containment_date"] = pd.to_datetime(
                df["containment_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        # ------------------------------------------------------------------
        # 6. Defensive re-filter: keep only 2024 California records
        #    (the upstream query already does this, but we guard here against
        #    any stale or mis-named files being passed in)
        # ------------------------------------------------------------------
        pre_filter_count = len(df)

        # Filter by state if the column exists (value: 'US-CA')
        if "state" in df.columns:
            df = df[df["state"].isin(["US-CA", "CA"])]

        # Filter by year in start_date
        if "start_date" in df.columns:
            df = df[
                df["start_date"].str.startswith("2024", na=False)
            ]

        faasr_log(
            f"clean_and_filter_data: {pre_filter_count} rows before "
            f"CA-2024 filter → {len(df)} rows after"
        )

        # ------------------------------------------------------------------
        # 6.5 Deduplicate on unique_fire_id: keep the single most complete
        #     and latest snapshot per fire.
        #
        #     WFIGS can emit multiple location-update records for the same
        #     fire (same UniqueFireIdentifier).  We sort each group so the
        #     "best" row lands last, then drop_duplicates(keep="last").
        #
        #     Sort order (ascending → last = best):
        #       1. _completeness  – count of non-null fields; more = better
        #       2. percent_contained – higher = later/more-complete update
        #       3. _has_containment – 1 if containment_date is present, else 0
        # ------------------------------------------------------------------
        if "unique_fire_id" in df.columns:
            pre_dedup_count = len(df)

            df["_completeness"] = df.notna().sum(axis=1)

            sort_keys = ["unique_fire_id", "_completeness"]
            if "percent_contained" in df.columns:
                sort_keys.append("percent_contained")
            if "containment_date" in df.columns:
                df["_has_containment"] = df["containment_date"].notna().astype(int)
                sort_keys.append("_has_containment")

            df = df.sort_values(sort_keys, ascending=True, na_position="first")
            df = df.drop_duplicates(subset=["unique_fire_id"], keep="last")
            df = df.drop(
                columns=[c for c in ["_completeness", "_has_containment"] if c in df.columns]
            )

            deduped = pre_dedup_count - len(df)
            if deduped:
                faasr_log(
                    f"clean_and_filter_data: removed {deduped} duplicate records "
                    "on unique_fire_id (kept most complete/latest snapshot per fire)"
                )

        # ------------------------------------------------------------------
        # 7. Drop rows missing critical location data (latitude or longitude)
        # ------------------------------------------------------------------
        pre_drop_count = len(df)
        location_cols = [c for c in ("latitude", "longitude") if c in df.columns]
        if location_cols:
            df = df.dropna(subset=location_cols)
        dropped = pre_drop_count - len(df)
        if dropped:
            faasr_log(
                f"clean_and_filter_data: dropped {dropped} rows with missing "
                "latitude/longitude"
            )

        # ------------------------------------------------------------------
        # 8. Guard: fail loudly if nothing survived cleaning
        # ------------------------------------------------------------------
        if df.empty:
            faasr_log(
                "clean_and_filter_data: 0 valid records remain after cleaning "
                "and filtering. Check upstream data quality — do NOT fabricate data."
            )
            raise RuntimeError(
                "No valid 2024 California wildfire records remain after "
                "cleaning. Cannot produce a cleaned output without real data."
            )

        faasr_log(
            f"clean_and_filter_data: {len(df)} clean records ready for output"
        )

        # ------------------------------------------------------------------
        # 9. Select and order the canonical output columns
        #    (keeping all columns that survived, but ensuring the key ones
        #    appear first for readability by downstream functions)
        # ------------------------------------------------------------------
        priority_cols = [
            "fire_name",
            "start_date",
            "containment_date",
            "acres_burned",
            "percent_contained",
            "latitude",
            "longitude",
            "county",
            "state",
            "fire_cause",
            "incident_type",
            "unique_fire_id",
        ]
        present_priority = [c for c in priority_cols if c in df.columns]
        remaining_cols = [c for c in df.columns if c not in priority_cols]
        df = df[present_priority + remaining_cols]

        # Reset index after all the filtering / dropping
        df = df.reset_index(drop=True)

        # ------------------------------------------------------------------
        # 10. Write cleaned CSV to a temp file, then upload to S3
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_out:
            tmp_output = tmp_out.name

        df.to_csv(tmp_output, index=False)

        faasr_log(
            f"clean_and_filter_data: uploading {output1} "
            f"({len(df)} records) to folder '{folder}'"
        )
        faasr_put_file(
            local_file=tmp_output,
            remote_folder=folder,
            remote_file=output1,
        )
        faasr_log(
            f"clean_and_filter_data: successfully uploaded {output1} "
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