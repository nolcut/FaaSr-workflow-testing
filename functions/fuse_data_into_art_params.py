import json
import os

import numpy as np


# --- CONTRACT HELPERS ---
def _faasr_requires(folder):
    if "weather_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Weather data file must be present in S3 before fusion can begin")
        raise SystemExit(1)
    if "astronomy_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Astronomy data file must be present in S3 before fusion can begin")
        raise SystemExit(1)
    if "financial_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[REQUIRE] CONTRACT VIOLATION: Financial data file must be present in S3 before fusion can begin")
        raise SystemExit(1)


def _faasr_promises(folder):
    if "art_params.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Fused art parameters JSON must be uploaded to S3 after successful fusion")
        raise SystemExit(1)
# --- end contract helpers ---


def fuse_data_into_art_params(
    folder: str, input1: str, input2: str, input3: str, output1: str
) -> None:
    """
    Reads weather, astronomy, and financial datasets from S3. Fuses them into a
    unified concrete scene parameter set by mapping data values to recognizable
    visual scene properties:
      - sky color and atmospheric conditions  <- temperature + weather code + humidity
      - celestial placement and brightness    <- astronomical magnitudes + moon phase + planet positions
      - scene activity and texture density    <- financial volatility + wind speed
      - foreground/background scene elements  <- market trend directions + seasonal context
    Writes the resulting concrete scene parameter dictionary as a JSON file to S3.
    """

    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting fusion of weather, astronomy, and financial data into concrete scene parameters")

    local_weather = "weather_data_fuse_local.json"
    local_astro = "astronomy_data_fuse_local.json"
    local_financial = "financial_data_fuse_local.json"
    local_output = "art_params_fuse_local.json"

    try:
        # -----------------------------------------------------------------------
        # Load input data from S3
        # -----------------------------------------------------------------------
        faasr_get_file(local_file=local_weather, remote_folder=folder, remote_file=input1)
        with open(local_weather) as f:
            weather = json.load(f)
        faasr_log(f"Loaded weather data from '{input1}'")

        faasr_get_file(local_file=local_astro, remote_folder=folder, remote_file=input2)
        with open(local_astro) as f:
            astronomy = json.load(f)
        faasr_log(f"Loaded astronomy data from '{input2}'")

        faasr_get_file(local_file=local_financial, remote_folder=folder, remote_file=input3)
        with open(local_financial) as f:
            financial = json.load(f)
        faasr_log(f"Loaded financial data from '{input3}'")

        # -----------------------------------------------------------------------
        # Validate required fields
        # -----------------------------------------------------------------------
        temperature = weather.get("temperature")
        if temperature is None:
            msg = f"Weather data ('{input1}') is missing required 'temperature' field"
            faasr_log(msg)
            raise RuntimeError(msg)

        weather_code = weather.get("weather_code")
        humidity = weather.get("humidity")
        wind_speed = weather.get("wind_speed")

        planets = astronomy.get("planets")
        if planets is None:
            msg = f"Astronomy data ('{input2}') is missing required 'planets' field"
            faasr_log(msg)
            raise RuntimeError(msg)

        moon_data = astronomy.get("moon")
        if moon_data is None:
            msg = f"Astronomy data ('{input2}') is missing required 'moon' field"
            faasr_log(msg)
            raise RuntimeError(msg)

        visible_constellations = astronomy.get("visible_constellations", [])

        assets = financial.get("assets")
        if not assets:
            msg = f"Financial data ('{input3}') is missing or empty 'assets' field"
            faasr_log(msg)
            raise RuntimeError(msg)

        # -----------------------------------------------------------------------
        # 1. SKY AND ATMOSPHERE — derived from temperature, weather code, humidity
        # -----------------------------------------------------------------------
        temperature = float(temperature)

        # Map temperature to sky color tone and colour temperature (Kelvin)
        # Cold sky appears bluish/icy; hot sky appears hazy and golden.
        if temperature < 0:
            sky_color_tone = "icy_blue"
            color_temperature_k = 8000
        elif temperature < 10:
            sky_color_tone = "pale_blue"
            color_temperature_k = 7000
        elif temperature < 20:
            sky_color_tone = "daylight_blue"
            color_temperature_k = 6500
        elif temperature < 30:
            sky_color_tone = "warm_azure"
            color_temperature_k = 5500
        else:
            sky_color_tone = "hazy_golden"
            color_temperature_k = 4500

        # WMO weather code → atmospheric condition, cloud coverage, visibility, precipitation
        wc = int(weather_code) if weather_code is not None else 0
        if wc == 0:
            atmospheric_condition = "clear"
            cloud_coverage = 0.0
            visibility = "excellent"
            precipitation = "none"
        elif 1 <= wc <= 2:
            atmospheric_condition = "partly_cloudy"
            cloud_coverage = 0.35
            visibility = "good"
            precipitation = "none"
        elif wc == 3:
            atmospheric_condition = "overcast"
            cloud_coverage = 0.90
            visibility = "moderate"
            precipitation = "none"
        elif 45 <= wc <= 48:
            atmospheric_condition = "foggy"
            cloud_coverage = 1.0
            visibility = "poor"
            precipitation = "none"
        elif 51 <= wc <= 55:
            atmospheric_condition = "drizzle"
            cloud_coverage = 0.80
            visibility = "moderate"
            precipitation = "light_rain"
        elif 61 <= wc <= 65:
            atmospheric_condition = "rainy"
            cloud_coverage = 0.90
            visibility = "low"
            precipitation = "rain"
        elif wc == 67 or (80 <= wc <= 82):
            atmospheric_condition = "heavy_rain"
            cloud_coverage = 1.0
            visibility = "poor"
            precipitation = "heavy_rain"
        elif 71 <= wc <= 77:
            atmospheric_condition = "snowy"
            cloud_coverage = 0.95
            visibility = "low"
            precipitation = "snow"
        elif 85 <= wc <= 86:
            atmospheric_condition = "snow_showers"
            cloud_coverage = 0.85
            visibility = "low"
            precipitation = "snow"
        elif 95 <= wc <= 99:
            atmospheric_condition = "stormy"
            cloud_coverage = 1.0
            visibility = "very_poor"
            precipitation = "heavy_rain_with_thunder"
        else:
            atmospheric_condition = "mixed"
            cloud_coverage = 0.50
            visibility = "moderate"
            precipitation = "none"

        # Humidity → atmospheric haze (high humidity = more diffuse, milky light)
        raw_humidity = float(humidity) if humidity is not None else 50.0
        haze_factor = float(np.clip(raw_humidity / 100.0, 0.0, 1.0))

        sky_atmosphere = {
            "sky_color_tone": sky_color_tone,
            "color_temperature_kelvin": color_temperature_k,
            "atmospheric_condition": atmospheric_condition,
            "cloud_coverage": round(cloud_coverage, 2),
            "visibility": visibility,
            "precipitation": precipitation,
            "haze_factor": round(haze_factor, 4),
            "source": {
                "temperature_c": temperature,
                "weather_code": wc,
                "humidity_pct": raw_humidity,
            },
        }

        faasr_log(
            f"Sky/atmosphere: condition={atmospheric_condition}, cloud_coverage={cloud_coverage:.2f}, "
            f"sky_color={sky_color_tone}, visibility={visibility}"
        )

        # -----------------------------------------------------------------------
        # 2. CELESTIAL PLACEMENT — derived from astronomical magnitudes & moon phase
        # -----------------------------------------------------------------------
        moon_phase_frac = float(moon_data.get("phase_fraction", 0.5))
        moon_illumination = float(moon_data.get("illumination_percent", 50.0))
        moon_phase_name = moon_data.get("phase_name", "Unknown")
        moon_is_visible = moon_data.get("is_visible", False)
        moon_alt_deg = float(moon_data.get("altitude_deg", 0.0))
        moon_az_deg = float(moon_data.get("azimuth_deg", 180.0))
        moon_constellation = moon_data.get("constellation", "")

        # Moon brightness: full illumination → very bright object in scene sky
        moon_brightness = float(np.clip(moon_illumination / 100.0, 0.0, 1.0))

        # Visible planets: collect those above the horizon with position + brightness
        visible_planet_details = []
        for planet_name, pdata in planets.items():
            if pdata.get("is_visible"):
                mag = pdata.get("magnitude")
                if mag is not None:
                    # Apparent magnitude: lower/more-negative = brighter
                    # Map from typical range [-5, 6] to [0, 1] brightness
                    brightness_norm = float(np.clip((6.0 - float(mag)) / 11.0, 0.0, 1.0))
                    visible_planet_details.append({
                        "name": planet_name,
                        "magnitude": round(float(mag), 2),
                        "brightness": round(brightness_norm, 4),
                        "altitude_deg": pdata.get("altitude_deg"),
                        "azimuth_deg": pdata.get("azimuth_deg"),
                        "constellation": pdata.get("constellation"),
                    })

        # Sort brightest-first so the image generator can prioritise prominent objects
        visible_planet_details.sort(key=lambda p: p["brightness"], reverse=True)

        n_constellations = len(visible_constellations)
        # Star-field density: more visible constellations → richer background sky
        star_field_density = float(np.clip(n_constellations / 20.0, 0.0, 1.0))

        celestial_placement = {
            "moon": {
                "is_visible": moon_is_visible,
                "phase_name": moon_phase_name,
                "phase_fraction": round(moon_phase_frac, 4),
                "brightness": round(moon_brightness, 4),
                "altitude_deg": round(moon_alt_deg, 4),
                "azimuth_deg": round(moon_az_deg, 4),
                "constellation": moon_constellation,
            },
            "visible_planets": visible_planet_details,
            "visible_constellations": visible_constellations,
            "star_field_density": round(star_field_density, 4),
            "n_visible_planets": len(visible_planet_details),
            "source": {
                "moon_illumination_pct": moon_illumination,
                "n_visible_constellations": n_constellations,
            },
        }

        faasr_log(
            f"Celestial: moon={moon_phase_name} ({moon_illumination:.1f}% illum, visible={moon_is_visible}), "
            f"{len(visible_planet_details)} visible planets, {n_constellations} constellations"
        )

        # -----------------------------------------------------------------------
        # 3. SCENE ACTIVITY AND TEXTURE DENSITY — from financial volatility + wind speed
        # -----------------------------------------------------------------------
        vol_values = []
        for symbol, adata in assets.items():
            v = adata.get("volatility_annualised")
            if v is not None:
                vol_values.append(float(v))

        if not vol_values:
            msg = "No 'volatility_annualised' values found in financial assets"
            faasr_log(msg)
            raise RuntimeError(msg)

        vol_arr = np.array(vol_values)
        mean_vol = float(np.mean(vol_arr))
        max_vol = float(np.max(vol_arr))

        # Normalise mean volatility to [0, 1]; ceiling at 2.0
        # Typical stocks: 0.2–0.5 annualised; crypto: 0.5–1.5+
        norm_vol = float(np.clip(mean_vol / 2.0, 0.0, 1.0))

        # High market volatility → busy, chaotic scene; low → calm, sparse scene
        if norm_vol < 0.20:
            activity_level = "serene"
            crowd_density = "empty"
            texture_density = "sparse"
        elif norm_vol < 0.50:
            activity_level = "moderate"
            crowd_density = "light"
            texture_density = "medium"
        elif norm_vol < 0.75:
            activity_level = "busy"
            crowd_density = "moderate"
            texture_density = "dense"
        else:
            activity_level = "frantic"
            crowd_density = "crowded"
            texture_density = "very_dense"

        # Wind speed → surface texture effects (water ripples, foliage sway, flags)
        raw_wind = float(wind_speed) if wind_speed is not None else 0.0
        if raw_wind < 10:
            wind_effect = "calm"
            surface_motion = "still"
        elif raw_wind < 30:
            wind_effect = "light_breeze"
            surface_motion = "gentle_ripples"
        elif raw_wind < 60:
            wind_effect = "moderate_wind"
            surface_motion = "active_movement"
        else:
            wind_effect = "strong_wind"
            surface_motion = "turbulent"

        scene_activity = {
            "activity_level": activity_level,
            "crowd_density": crowd_density,
            "texture_density": texture_density,
            "normalized_market_volatility": round(norm_vol, 4),
            "wind_effect": wind_effect,
            "surface_motion": surface_motion,
            "source": {
                "mean_volatility_annualised": round(mean_vol, 6),
                "max_volatility_annualised": round(max_vol, 6),
                "wind_speed_kmh": raw_wind,
            },
        }

        faasr_log(
            f"Scene activity: level={activity_level}, crowd={crowd_density}, "
            f"texture={texture_density}, wind_effect={wind_effect}"
        )

        # -----------------------------------------------------------------------
        # 4. SCENE ELEMENTS — from market trend direction + seasonal context
        # -----------------------------------------------------------------------
        bullish_count = sum(1 for a in assets.values() if a.get("trend") == "bullish")
        bearish_count = sum(1 for a in assets.values() if a.get("trend") == "bearish")
        total_assets = len(assets)

        bullish_ratio = bullish_count / total_assets if total_assets > 0 else 0.5

        # Scene type: bullish markets → upward urban scenes (skyscrapers, construction);
        # bearish markets → horizontal/downward natural landscapes; mixed → suburban
        if bullish_ratio > 0.6:
            scene_type = "urban_cityscape"
            scene_orientation = "upward"
            market_sentiment = "bullish"
            foreground_elements = ["pedestrians", "street_traffic", "lit_storefronts", "trees_lining_street"]
            background_elements = ["tall_skyscrapers", "cranes_construction", "illuminated_office_towers"]
        elif (1.0 - bullish_ratio) > 0.6:
            scene_type = "rural_landscape"
            scene_orientation = "horizontal"
            market_sentiment = "bearish"
            foreground_elements = ["rolling_hills", "winding_river", "sparse_trees", "dirt_path"]
            background_elements = ["mountain_range", "forest_treeline", "distant_farmland"]
        else:
            scene_type = "suburban_townscape"
            scene_orientation = "balanced"
            market_sentiment = "mixed"
            foreground_elements = ["residential_street", "parked_cars", "garden_hedges", "lamp_posts"]
            background_elements = ["low_rise_buildings", "church_steeple", "water_tower", "distant_hills"]

        # Determine season from the astronomy timestamp (UTC); observer is New York City (northern hemisphere)
        astronomy_ts = astronomy.get("timestamp_utc", "")
        season = "unknown"
        if astronomy_ts:
            try:
                month = int(astronomy_ts[5:7])
                if month in (12, 1, 2):
                    season = "winter"
                elif month in (3, 4, 5):
                    season = "spring"
                elif month in (6, 7, 8):
                    season = "summer"
                else:
                    season = "autumn"
            except (ValueError, IndexError):
                pass
        if season == "unknown" and weather.get("time"):
            try:
                month = int(str(weather.get("time", ""))[5:7])
                if month in (12, 1, 2):
                    season = "winter"
                elif month in (3, 4, 5):
                    season = "spring"
                elif month in (6, 7, 8):
                    season = "summer"
                else:
                    season = "autumn"
            except (ValueError, IndexError):
                pass

        # Season-specific scene modifiers: vegetation state, lighting angle, ground cover
        season_modifier_map = {
            "winter": {"vegetation": "bare_trees", "lighting": "low_angle_cold", "ground_cover": "snow_or_frost"},
            "spring": {"vegetation": "budding_trees", "lighting": "fresh_daylight", "ground_cover": "new_grass"},
            "summer": {"vegetation": "full_foliage", "lighting": "bright_high_sun", "ground_cover": "lush_grass"},
            "autumn": {"vegetation": "autumn_coloured_trees", "lighting": "golden_hour_warm", "ground_cover": "fallen_leaves"},
            "unknown": {"vegetation": "generic_trees", "lighting": "natural_daylight", "ground_cover": "grass"},
        }
        seasonal_modifiers = season_modifier_map.get(season, season_modifier_map["unknown"])

        # Time of day: infer from moon visibility and altitude vs cloud coverage
        if moon_is_visible and moon_alt_deg > 10 and cloud_coverage < 0.7:
            time_of_day = "night"
            lighting_quality = "moonlit"
        elif moon_is_visible and moon_alt_deg <= 10:
            time_of_day = "twilight"
            lighting_quality = "dusk_or_dawn"
        else:
            # Moon below horizon → daytime; lighting quality driven by cloud coverage
            if cloud_coverage < 0.3:
                time_of_day = "daytime"
                lighting_quality = "clear_sunlight"
            elif cloud_coverage < 0.7:
                time_of_day = "daytime"
                lighting_quality = "diffuse_overcast"
            else:
                time_of_day = "daytime"
                lighting_quality = "flat_overcast"

        asset_trends = {
            symbol: adata.get("trend", "unknown")
            for symbol, adata in assets.items()
        }

        scene_elements = {
            "scene_type": scene_type,
            "scene_orientation": scene_orientation,
            "time_of_day": time_of_day,
            "lighting_quality": lighting_quality,
            "season": season,
            "seasonal_modifiers": seasonal_modifiers,
            "foreground_elements": foreground_elements,
            "background_elements": background_elements,
            "market_sentiment": market_sentiment,
            "asset_trends": asset_trends,
            "source": {
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "total_assets": total_assets,
                "moon_visible": moon_is_visible,
                "moon_alt_deg": round(moon_alt_deg, 4),
                "cloud_coverage": round(cloud_coverage, 2),
            },
        }

        faasr_log(
            f"Scene elements: type={scene_type}, time={time_of_day}, season={season}, "
            f"lighting={lighting_quality}, market_sentiment={market_sentiment}"
        )

        # -----------------------------------------------------------------------
        # Assemble unified concrete scene parameter set
        # -----------------------------------------------------------------------
        art_params = {
            "sky_atmosphere": sky_atmosphere,
            "celestial_placement": celestial_placement,
            "scene_activity": scene_activity,
            "scene_elements": scene_elements,
            "metadata": {
                "weather_time": weather.get("time"),
                "astronomy_timestamp": astronomy.get("timestamp_utc"),
                "financial_timestamp": financial.get("timestamp_utc"),
                "observer_location": astronomy.get("observer", {}).get("location"),
            },
        }

        # -----------------------------------------------------------------------
        # Write and upload to S3
        # -----------------------------------------------------------------------
        with open(local_output, "w") as f:
            json.dump(art_params, f, indent=2)

        faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
        faasr_log(f"Concrete scene parameters uploaded to S3 folder '{folder}' as '{output1}'")

    finally:
        for tmp in [local_weather, local_astro, local_financial, local_output]:
            if os.path.exists(tmp):
                os.remove(tmp)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---