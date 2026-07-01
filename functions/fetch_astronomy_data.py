import datetime
import json
import math
import os

import ephem


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "astronomy_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Astronomy data JSON file was not uploaded to S3 after computation")
        raise SystemExit(1)
# --- end contract helpers ---


def fetch_astronomy_data(folder: str, output1: str) -> None:
    """
    Fetches current astronomy data using the ephem library.
    Computes moon phase, planetary positions, and visible constellations
    for today's date from a representative observer location (New York City).
    Saves collected astronomy data as a JSON file to S3.
    """

    faasr_log("Computing astronomy data using ephem library")

    # Representative observer location: New York City
    observer = ephem.Observer()
    observer.lat = "40.7128"
    observer.lon = "-74.0060"
    observer.elevation = 10
    observer.date = ephem.now()

    now_utc = datetime.datetime.utcnow()
    faasr_log(f"Computing astronomy data for UTC time: {now_utc.isoformat()}")

    # ------------------------------------------------------------------
    # Moon Phase
    # ------------------------------------------------------------------
    moon = ephem.Moon(observer)

    moon_alt_deg = math.degrees(float(moon.alt))
    moon_az_deg = math.degrees(float(moon.az))
    moon_is_visible = moon_alt_deg > 0

    # Determine waxing vs waning by comparing tomorrow's illumination
    future_obs = ephem.Observer()
    future_obs.lat = observer.lat
    future_obs.lon = observer.lon
    future_obs.elevation = observer.elevation
    future_obs.date = ephem.date(observer.date + 1)
    future_moon = ephem.Moon(future_obs)
    waxing = future_moon.phase > moon.phase

    phase_frac = moon.phase / 100.0
    if phase_frac < 0.02:
        phase_name = "New Moon"
    elif phase_frac < 0.48:
        phase_name = "Waxing Crescent" if waxing else "Waning Crescent"
    elif phase_frac < 0.52:
        phase_name = "First Quarter" if waxing else "Last Quarter"
    elif phase_frac < 0.98:
        phase_name = "Waxing Gibbous" if waxing else "Waning Gibbous"
    else:
        phase_name = "Full Moon"

    moon_constellation = ephem.constellation(moon)[1]

    moon_data = {
        "phase_fraction": round(phase_frac, 4),
        "phase_name": phase_name,
        "illumination_percent": round(float(moon.phase), 2),
        "ra": str(moon.ra),
        "dec": str(moon.dec),
        "altitude_deg": round(moon_alt_deg, 4),
        "azimuth_deg": round(moon_az_deg, 4),
        "is_visible": moon_is_visible,
        "constellation": moon_constellation,
    }

    faasr_log(
        f"Moon: {phase_name} ({moon.phase:.1f}% illuminated), "
        f"alt={moon_alt_deg:.1f}°, constellation={moon_constellation}"
    )

    # ------------------------------------------------------------------
    # Planetary Positions
    # ------------------------------------------------------------------
    planet_classes = [
        ("Mercury", ephem.Mercury),
        ("Venus", ephem.Venus),
        ("Mars", ephem.Mars),
        ("Jupiter", ephem.Jupiter),
        ("Saturn", ephem.Saturn),
        ("Uranus", ephem.Uranus),
        ("Neptune", ephem.Neptune),
    ]

    planetary_positions = {}
    for name, PlanetClass in planet_classes:
        planet = PlanetClass(observer)
        alt_deg = math.degrees(float(planet.alt))
        az_deg = math.degrees(float(planet.az))
        constellation = ephem.constellation(planet)[1]
        planetary_positions[name] = {
            "ra": str(planet.ra),
            "dec": str(planet.dec),
            "altitude_deg": round(alt_deg, 4),
            "azimuth_deg": round(az_deg, 4),
            "is_visible": alt_deg > 0,
            "constellation": constellation,
            "magnitude": round(float(planet.mag), 2),
        }
        faasr_log(
            f"{name}: alt={alt_deg:.1f}°, az={az_deg:.1f}°, "
            f"constellation={constellation}, mag={planet.mag:.1f}"
        )

    # ------------------------------------------------------------------
    # Visible Constellations
    # Seed from visible planets and moon, then enrich with bright stars.
    # ------------------------------------------------------------------
    visible_const_set: set = set()
    for pos in planetary_positions.values():
        if pos["is_visible"]:
            visible_const_set.add(pos["constellation"])
    if moon_is_visible:
        visible_const_set.add(moon_constellation)

    # Well-known bright stars whose names are in ephem's built-in catalog
    bright_star_names = [
        "Sirius",
        "Canopus",
        "Arcturus",
        "Vega",
        "Capella",
        "Rigel",
        "Procyon",
        "Achernar",
        "Betelgeuse",
        "Hadar",
        "Altair",
        "Acrux",
        "Aldebaran",
        "Antares",
        "Spica",
        "Pollux",
        "Fomalhaut",
        "Deneb",
        "Mimosa",
        "Regulus",
    ]

    for star_name in bright_star_names:
        try:
            star = ephem.star(star_name)
            star.compute(observer)
            alt_deg = math.degrees(float(star.alt))
            if alt_deg > 5:  # well above the horizon
                const = ephem.constellation(star)[1]
                visible_const_set.add(const)
        except KeyError:
            # Star name not in ephem's built-in catalog — skip without fabricating data
            faasr_log(f"Warning: star '{star_name}' not found in ephem catalog; skipping")

    visible_constellations = sorted(visible_const_set)
    faasr_log(
        f"Visible constellations ({len(visible_constellations)}): "
        f"{', '.join(visible_constellations)}"
    )

    # ------------------------------------------------------------------
    # Compile result and upload
    # ------------------------------------------------------------------
    astronomy_data = {
        "timestamp_utc": now_utc.isoformat() + "Z",
        "observer": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "location": "New York City, USA",
        },
        "moon": moon_data,
        "planets": planetary_positions,
        "visible_constellations": visible_constellations,
    }

    local_file = "astronomy_data_local.json"
    try:
        with open(local_file, "w") as f:
            json.dump(astronomy_data, f, indent=2)

        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Astronomy data uploaded to S3 folder '{folder}' as '{output1}'")
    finally:
        if os.path.exists(local_file):
            os.remove(local_file)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---