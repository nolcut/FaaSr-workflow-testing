import json
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must precede pyplot import
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "cleaned_wildfire_data_2024.csv" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Wildfire CSV input missing from S3; cannot build map or charts without fire records")
        raise SystemExit(1)
    if "wildfire_statistics_2024.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Wildfire statistics JSON missing from S3; cannot annotate figure or build monthly/top-10 charts")
        raise SystemExit(1)
    if "california_state_boundary.geojson" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: California state boundary GeoJSON missing from S3; cannot render base map")
        raise SystemExit(1)
    if "california_county_boundaries.geojson" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: California county boundaries GeoJSON missing from S3; cannot render county overlay on map")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "california_wildfires_2024_visualization.png" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Multi-panel visualization PNG was not uploaded to S3 after figure generation")
        raise SystemExit(1)
# --- end contract helpers ---


def generate_visualization(
    folder: str,
    input1: str,   # cleaned_wildfire_data_2024.csv
    input2: str,   # wildfire_statistics_2024.json
    input3: str,   # california_state_boundary.geojson
    input4: str,   # california_county_boundaries.geojson
    output1: str,  # california_wildfires_2024_visualization.png
) -> None:
    """
    Read the cleaned 2024 California wildfire CSV, wildfire statistics JSON,
    and California boundary GeoJSON files from S3.  Produce a multi-panel
    high-resolution PNG with:
      Panel 1 – California map with fire-location bubbles scaled by acres burned
      Panel 2 – Monthly total acres-burned bar chart
      Panel 3 – Top-10 fires ranked by acres burned (horizontal bar chart)
    Upload the finished figure to S3.
    """
    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("generate_visualization: starting visualization pipeline")

    tmp_csv = None
    tmp_json = None
    tmp_state = None
    tmp_county = None
    tmp_png = None

    try:
        # ------------------------------------------------------------------
        # 1. Allocate temp files for all inputs/output
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp_csv = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_json = f.name
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as f:
            tmp_state = f.name
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as f:
            tmp_county = f.name

        # ------------------------------------------------------------------
        # 2. Download all four input files from S3
        # ------------------------------------------------------------------
        faasr_log(f"generate_visualization: downloading {input1} from folder '{folder}'")
        faasr_get_file(local_file=tmp_csv, remote_folder=folder, remote_file=input1)

        faasr_log(f"generate_visualization: downloading {input2} from folder '{folder}'")
        faasr_get_file(local_file=tmp_json, remote_folder=folder, remote_file=input2)

        faasr_log(f"generate_visualization: downloading {input3} from folder '{folder}'")
        faasr_get_file(local_file=tmp_state, remote_folder=folder, remote_file=input3)

        faasr_log(f"generate_visualization: downloading {input4} from folder '{folder}'")
        faasr_get_file(local_file=tmp_county, remote_folder=folder, remote_file=input4)

        # ------------------------------------------------------------------
        # 3. Load and validate wildfire CSV
        # ------------------------------------------------------------------
        faasr_log("generate_visualization: parsing wildfire CSV")
        try:
            df = pd.read_csv(tmp_csv)
        except Exception as exc:
            faasr_log(f"generate_visualization: cannot parse {input1} as CSV: {exc}")
            raise RuntimeError(f"Cannot parse {input1} as CSV: {exc}") from exc

        if df.empty:
            faasr_log(
                "generate_visualization: wildfire CSV is empty — "
                "cannot visualize without real data"
            )
            raise RuntimeError(
                f"{input1} contains no records. Cannot produce visualization "
                "without real wildfire data."
            )

        faasr_log(
            f"generate_visualization: loaded {len(df)} wildfire records; "
            f"columns: {list(df.columns)}"
        )

        # Coerce numeric fields
        for col in ("acres_burned", "latitude", "longitude"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Parse start_date into datetime for grouping
        if "start_date" in df.columns:
            df["start_date_dt"] = pd.to_datetime(df["start_date"], errors="coerce")
        else:
            df["start_date_dt"] = pd.NaT

        # ------------------------------------------------------------------
        # 4. Load and validate wildfire statistics JSON
        # ------------------------------------------------------------------
        faasr_log("generate_visualization: parsing wildfire statistics JSON")
        try:
            with open(tmp_json, "r", encoding="utf-8") as fh:
                stats = json.load(fh)
        except Exception as exc:
            faasr_log(f"generate_visualization: cannot parse {input2} as JSON: {exc}")
            raise RuntimeError(f"Cannot parse {input2} as JSON: {exc}") from exc

        if not isinstance(stats, dict):
            faasr_log("generate_visualization: statistics JSON is not a dict object")
            raise RuntimeError(
                f"{input2} does not contain a valid statistics dictionary."
            )

        # --- Monthly burn data ---
        # Primary source: pre-computed monthly_acres_burned from compute_statistics.py
        # Fallback: aggregate directly from the cleaned CSV (still real data)
        monthly_data = stats.get("monthly_acres_burned", [])
        if not monthly_data:
            faasr_log(
                "generate_visualization: monthly_acres_burned absent from stats JSON "
                "— computing from wildfire CSV"
            )
            required_cols_monthly = {"start_date_dt", "acres_burned"}
            if required_cols_monthly.issubset(set(df.columns)):
                month_agg = (
                    df.dropna(subset=["start_date_dt", "acres_burned"])
                    .assign(year_month=lambda d: d["start_date_dt"].dt.strftime("%Y-%m"))
                    .groupby("year_month", sort=True)["acres_burned"]
                    .sum()
                    .reset_index()
                )
                month_agg.columns = ["month", "total_acres_burned"]
                monthly_data = month_agg.to_dict("records")

        if not monthly_data:
            faasr_log(
                "generate_visualization: no monthly acreage data available in stats "
                "JSON or CSV — cannot produce monthly bar chart"
            )
            raise RuntimeError(
                "No monthly_acres_burned data available. "
                "Cannot produce bar chart without real data."
            )

        # --- Top-10 fires data ---
        top10_data = stats.get("top_10_fires_by_size", [])
        if not top10_data:
            faasr_log(
                "generate_visualization: top_10_fires_by_size absent from stats JSON "
                "— computing from wildfire CSV"
            )
            if "acres_burned" in df.columns:
                top10_df = (
                    df.dropna(subset=["acres_burned"])
                    .nlargest(10, "acres_burned")
                    .reset_index(drop=True)
                )
                top10_data = [
                    {
                        "rank": i + 1,
                        "fire_name": str(
                            row.get("fire_name") if pd.notna(row.get("fire_name")) else f"Fire #{i + 1}"
                        ),
                        "acres_burned": float(row["acres_burned"]),
                    }
                    for i, (_, row) in enumerate(top10_df.iterrows())
                ]

        if not top10_data:
            faasr_log(
                "generate_visualization: no top-10 fire data available in stats "
                "JSON or CSV — cannot produce ranked bar chart"
            )
            raise RuntimeError(
                "No top_10_fires_by_size data available. "
                "Cannot produce bar chart without real data."
            )

        # Summary totals for figure annotations
        summary = stats.get("summary", {})
        total_fires = summary.get("total_fires", len(df))
        total_acres = summary.get(
            "total_acres_burned",
            float(df["acres_burned"].sum(skipna=True)) if "acres_burned" in df.columns else 0.0,
        )

        # ------------------------------------------------------------------
        # 5. Load and validate California boundary GeoJSON files
        # ------------------------------------------------------------------
        faasr_log("generate_visualization: loading California state boundary GeoJSON")
        try:
            state_gdf = gpd.read_file(tmp_state)
        except Exception as exc:
            faasr_log(f"generate_visualization: cannot load {input3} as GeoJSON: {exc}")
            raise RuntimeError(f"Cannot load {input3} as GeoJSON: {exc}") from exc

        if state_gdf.empty:
            faasr_log("generate_visualization: state boundary GeoJSON has no features")
            raise RuntimeError(
                f"{input3} contains no geographic features. "
                "Cannot render map without real boundary data."
            )

        faasr_log("generate_visualization: loading California county boundaries GeoJSON")
        try:
            county_gdf = gpd.read_file(tmp_county)
        except Exception as exc:
            faasr_log(f"generate_visualization: cannot load {input4} as GeoJSON: {exc}")
            raise RuntimeError(f"Cannot load {input4} as GeoJSON: {exc}") from exc

        if county_gdf.empty:
            faasr_log("generate_visualization: county boundary GeoJSON has no features")
            raise RuntimeError(
                f"{input4} contains no geographic features. "
                "Cannot render map without real boundary data."
            )

        # ------------------------------------------------------------------
        # 6. Reproject geographic data to California Albers (EPSG:3310)
        # ------------------------------------------------------------------
        target_crs = "EPSG:3310"
        faasr_log(f"generate_visualization: reprojecting to {target_crs}")

        try:
            state_proj = state_gdf.to_crs(target_crs)
            county_proj = county_gdf.to_crs(target_crs)
        except Exception as exc:
            faasr_log(f"generate_visualization: CRS reprojection failed for boundary layers: {exc}")
            raise RuntimeError(
                f"CRS reprojection to {target_crs} failed for boundary layers: {exc}"
            ) from exc

        # Build a GeoDataFrame of fire locations
        fires_for_map = df.dropna(subset=["latitude", "longitude", "acres_burned"]).copy()
        fires_for_map = fires_for_map[fires_for_map["acres_burned"] > 0].reset_index(drop=True)

        if fires_for_map.empty:
            faasr_log(
                "generate_visualization: no fires with valid lat/lon and positive "
                "acres_burned — cannot render bubble map"
            )
            raise RuntimeError(
                "No fires with valid latitude, longitude, and acres_burned > 0. "
                "Cannot produce map without real location data."
            )

        fire_pts = gpd.GeoDataFrame(
            fires_for_map,
            geometry=[
                Point(row["longitude"], row["latitude"])
                for _, row in fires_for_map.iterrows()
            ],
            crs="EPSG:4326",
        )
        try:
            fire_pts_proj = fire_pts.to_crs(target_crs)
        except Exception as exc:
            faasr_log(f"generate_visualization: CRS reprojection failed for fire points: {exc}")
            raise RuntimeError(
                f"CRS reprojection of fire points to {target_crs} failed: {exc}"
            ) from exc

        faasr_log(f"generate_visualization: {len(fire_pts_proj)} fire points ready for map")

        # ------------------------------------------------------------------
        # 7. Prepare chart data
        # ------------------------------------------------------------------

        # Monthly bar chart labels and values
        monthly_labels = []
        monthly_acres_vals = []
        for entry in monthly_data:
            month_str = str(entry.get("month", ""))
            try:
                label = pd.Timestamp(month_str + "-01").strftime("%b\n%Y")
            except Exception:
                label = month_str
            monthly_labels.append(label)
            monthly_acres_vals.append(float(entry.get("total_acres_burned", 0.0)))

        # Top-10 bar chart: ascending order so the largest fire sits at the top
        top10_sorted = sorted(top10_data, key=lambda x: float(x.get("acres_burned", 0.0)))
        top10_names = []
        top10_acres_vals = []
        for entry in top10_sorted:
            raw_name = entry.get("fire_name") or "Unknown"
            name = str(raw_name).strip()
            if len(name) > 28:
                name = name[:25] + "…"
            top10_names.append(name)
            top10_acres_vals.append(float(entry.get("acres_burned", 0.0)))

        # ------------------------------------------------------------------
        # 8. Build multi-panel figure
        # ------------------------------------------------------------------
        faasr_log("generate_visualization: composing multi-panel figure")

        fig = plt.figure(figsize=(22, 14), dpi=150)
        fig.patch.set_facecolor("#f5f5ee")

        # GridSpec: left column = map (spans both rows), right = two charts
        gs = fig.add_gridspec(
            nrows=2, ncols=2,
            width_ratios=[1.2, 0.8],
            height_ratios=[1, 1],
            left=0.04, right=0.97,
            top=0.89, bottom=0.07,
            hspace=0.44, wspace=0.26,
        )
        ax_map = fig.add_subplot(gs[:, 0])       # Map spans both rows
        ax_monthly = fig.add_subplot(gs[0, 1])   # Monthly bar chart
        ax_top10 = fig.add_subplot(gs[1, 1])     # Top-10 horizontal bar chart

        # ============================================================
        # Panel 1: Map of California with fire-location bubbles
        # ============================================================
        ax_map.set_facecolor("#b8d4e8")  # Background colour (ocean / off-map)

        state_proj.plot(
            ax=ax_map,
            color="#ede8d8",
            edgecolor="#555555",
            linewidth=1.0,
            zorder=2,
        )
        county_proj.plot(
            ax=ax_map,
            color="none",
            edgecolor="#aaaaaa",
            linewidth=0.35,
            zorder=3,
        )

        # Scale bubble area by sqrt(acres) so large fires don't overwhelm the map
        acres_arr = fire_pts_proj["acres_burned"].values.astype(float)
        max_acres = float(acres_arr.max())
        bubble_sizes = (np.sqrt(acres_arr / max_acres) * 500.0).clip(min=8.0)

        # Log-normalised colour scale
        vmin_val = float(max(np.nanmin(acres_arr), 1.0))
        vmax_val = float(max_acres)
        if vmax_val <= vmin_val:
            vmax_val = vmin_val + 1.0
        log_norm = mcolors.LogNorm(vmin=vmin_val, vmax=vmax_val)

        sc = ax_map.scatter(
            fire_pts_proj.geometry.x,
            fire_pts_proj.geometry.y,
            s=bubble_sizes,
            c=acres_arr,
            cmap="YlOrRd",
            norm=log_norm,
            alpha=0.78,
            edgecolors="#333333",
            linewidths=0.4,
            zorder=4,
        )

        cbar = fig.colorbar(sc, ax=ax_map, orientation="vertical", shrink=0.55, pad=0.02)
        cbar.set_label("Acres Burned (log scale)", fontsize=8)
        cbar.ax.tick_params(labelsize=7)

        # Bubble-size legend (representative acreage values)
        legend_acre_vals = [
            a for a in [100, 1_000, 10_000, 100_000]
            if a <= max_acres * 1.05
        ]
        legend_handles = [
            ax_map.scatter(
                [], [],
                s=float(max(np.sqrt(a / max_acres) * 500.0, 8.0)),
                c="#d73027",
                alpha=0.75,
                edgecolors="#333333",
                linewidths=0.4,
                label=f"{a:,} ac",
            )
            for a in legend_acre_vals
        ]
        if legend_handles:
            ax_map.legend(
                handles=legend_handles,
                title="Fire Size",
                title_fontsize=8,
                fontsize=7,
                loc="lower left",
                framealpha=0.88,
                edgecolor="#bbbbbb",
            )

        # Set map extent from state boundary + 5 % margin
        minx, miny, maxx, maxy = state_proj.total_bounds
        mx = (maxx - minx) * 0.05
        my = (maxy - miny) * 0.05
        ax_map.set_xlim(minx - mx, maxx + mx)
        ax_map.set_ylim(miny - my, maxy + my)

        ax_map.set_title(
            "2024 California Wildfire Locations\n"
            "(bubble size ∝ acres burned)",
            fontsize=12, fontweight="bold", pad=8,
        )
        ax_map.set_xlabel("Easting — CA Albers (m)", fontsize=7.5)
        ax_map.set_ylabel("Northing — CA Albers (m)", fontsize=7.5)
        ax_map.tick_params(labelsize=7)

        # Optional: basemap tiles from contextily
        try:
            import contextily as ctx
            ctx.add_basemap(
                ax_map,
                crs=target_crs,
                source=ctx.providers.CartoDB.Positron,
                alpha=0.45,
                zorder=1,
            )
            faasr_log("generate_visualization: basemap tiles added")
        except Exception as tile_exc:
            faasr_log(
                f"generate_visualization: basemap tile fetch skipped — {tile_exc}"
            )
            # State and county boundaries already provide geographic context;
            # skipping tiles does not alter any scientific data.

        # ============================================================
        # Panel 2: Monthly total acres-burned bar chart
        # ============================================================
        n_months = len(monthly_labels)
        bar_colors_m = plt.cm.YlOrRd(np.linspace(0.2, 0.9, max(n_months, 1)))
        bars_m = ax_monthly.bar(
            range(n_months),
            monthly_acres_vals,
            color=bar_colors_m,
            edgecolor="#555555",
            linewidth=0.5,
        )
        ax_monthly.set_xticks(range(n_months))
        ax_monthly.set_xticklabels(monthly_labels, rotation=0, ha="center", fontsize=7.5)

        max_monthly = max(monthly_acres_vals) if monthly_acres_vals else 1.0
        for bar, val in zip(bars_m, monthly_acres_vals):
            if val > 0:
                ax_monthly.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    val + max_monthly * 0.012,
                    f"{val:,.0f}",
                    ha="center", va="bottom", fontsize=6.0, color="#333333",
                )

        ax_monthly.set_title(
            "Monthly Total Acres Burned — 2024",
            fontsize=11, fontweight="bold", pad=6,
        )
        ax_monthly.set_ylabel("Total Acres Burned", fontsize=9)
        ax_monthly.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{x:,.0f}")
        )
        ax_monthly.tick_params(axis="y", labelsize=7.5)
        ax_monthly.set_facecolor("#fafaf5")
        ax_monthly.spines[["top", "right"]].set_visible(False)
        ax_monthly.grid(axis="y", linestyle="--", alpha=0.35, zorder=0)

        # ============================================================
        # Panel 3: Top-10 fires horizontal ranked bar chart
        # ============================================================
        n_top10 = len(top10_names)
        bar_colors_t = plt.cm.YlOrRd(np.linspace(0.2, 0.9, max(n_top10, 1)))
        y_pos = np.arange(n_top10)
        hbars = ax_top10.barh(
            y_pos,
            top10_acres_vals,
            color=bar_colors_t,
            edgecolor="#555555",
            linewidth=0.5,
        )
        ax_top10.set_yticks(y_pos)
        ax_top10.set_yticklabels(top10_names, fontsize=7.5)

        max_top10 = max(top10_acres_vals) if top10_acres_vals else 1.0
        for bar, val in zip(hbars, top10_acres_vals):
            ax_top10.text(
                val + max_top10 * 0.01,
                bar.get_y() + bar.get_height() / 2.0,
                f"{val:,.0f} ac",
                va="center", ha="left", fontsize=6.5, color="#333333",
            )

        ax_top10.set_title(
            "Top 10 Fires by Acres Burned — 2024",
            fontsize=11, fontweight="bold", pad=6,
        )
        ax_top10.set_xlabel("Acres Burned", fontsize=9)
        ax_top10.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"{x:,.0f}")
        )
        ax_top10.tick_params(axis="x", labelsize=7.5)
        ax_top10.set_xlim(0, max_top10 * 1.22)
        ax_top10.set_facecolor("#fafaf5")
        ax_top10.spines[["top", "right"]].set_visible(False)
        ax_top10.grid(axis="x", linestyle="--", alpha=0.35, zorder=0)

        # ============================================================
        # Overall figure title and data-source annotation
        # ============================================================
        fig.suptitle(
            "2024 California Wildfire Analysis",
            fontsize=19, fontweight="bold", y=0.965, color="#1a1a1a",
        )
        fig.text(
            0.5, 0.924,
            (
                f"Total Incidents: {total_fires:,}  |  "
                f"Total Acres Burned: {total_acres:,.0f}  |  "
                "Sources: NIFC WFIGS & US Census Bureau TIGERweb"
            ),
            ha="center", va="top", fontsize=9, color="#555555", style="italic",
        )

        # ------------------------------------------------------------------
        # 9. Save figure to temp PNG and upload to S3
        # ------------------------------------------------------------------
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_png = f.name

        faasr_log("generate_visualization: saving figure to temp PNG")
        fig.savefig(tmp_png, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        faasr_log(
            f"generate_visualization: uploading {output1} to folder '{folder}'"
        )
        faasr_put_file(local_file=tmp_png, remote_folder=folder, remote_file=output1)
        faasr_log(f"generate_visualization: successfully uploaded {output1}")

    finally:
        for path in (tmp_csv, tmp_json, tmp_state, tmp_county, tmp_png):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---