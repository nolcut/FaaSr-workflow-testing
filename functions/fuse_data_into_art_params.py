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
    unified abstract art parameter set by mapping data values to visual properties:
      - color palettes      ← temperature + weather code + humidity
      - shape distributions ← astronomical magnitudes + moon phase + constellation count
      - textures            ← financial volatility + wind speed
      - compositional rules ← market trend directions + moon phase + temperature
    Writes the resulting art parameter dictionary as a JSON file to S3.
    """

    # --- CONTRACT: requires ---
    _faasr_requires(folder)
    # --- end requires ---
    faasr_log("Starting fusion of weather, astronomy, and financial data into art parameters")

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
        # 1. COLOR PALETTE — derived from temperature, weather code, and humidity
        # -----------------------------------------------------------------------
        temperature = float(temperature)

        # Map temperature to hue range (degrees on the HSV wheel, 0–360)
        # Cold  (<   0 °C): blue-violet     [220 – 270]
        # Cool  (0 – 15 °C): teal-cyan-green [150 – 210]
        # Warm  (15 – 30 °C): yellow-orange   [ 30 –  90]
        # Hot   (>  30 °C): red-orange       [  0 –  30]
        if temperature < 0:
            hue_min, hue_max = 220, 270
            base_palette_name = "arctic"
            palette_mood = "cold"
        elif temperature < 15:
            hue_min, hue_max = 150, 210
            base_palette_name = "cool"
            palette_mood = "cool"
        elif temperature < 30:
            hue_min, hue_max = 30, 90
            base_palette_name = "warm"
            palette_mood = "warm"
        else:
            hue_min, hue_max = 0, 30
            base_palette_name = "hot"
            palette_mood = "hot"

        # Saturation: high humidity mutes colours (shifts toward grey)
        # humidity in [0, 100] → saturation in [0.5, 1.0]
        raw_humidity = float(humidity) if humidity is not None else 50.0
        saturation = 1.0 - raw_humidity / 200.0
        saturation = float(np.clip(saturation, 0.3, 1.0))

        # Brightness driven by weather code (WMO classification)
        wc = int(weather_code) if weather_code is not None else 0
        if wc == 0:
            brightness, overlay_effect = 0.95, "none"
        elif 1 <= wc <= 3:
            brightness, overlay_effect = 0.85, "light_cloud"
        elif 45 <= wc <= 48:
            brightness, overlay_effect = 0.55, "fog"
        elif (51 <= wc <= 67) or (80 <= wc <= 82):
            brightness, overlay_effect = 0.70, "rain"
        elif (71 <= wc <= 77) or (85 <= wc <= 86):
            brightness, overlay_effect = 0.80, "snow"
        elif 95 <= wc <= 99:
            brightness, overlay_effect = 0.50, "storm"
        else:
            brightness, overlay_effect = 0.75, "mixed"

        # Five evenly-spaced hues across the mapped range
        hues = np.linspace(hue_min, hue_max, 5).tolist()

        color_palette = {
            "base_palette_name": base_palette_name,
            "palette_mood": palette_mood,
            "hue_range": [hue_min, hue_max],
            "hues_degrees": [round(h, 2) for h in hues],
            "saturation": round(saturation, 4),
            "brightness": round(brightness, 4),
            "overlay_effect": overlay_effect,
            "source": {
                "temperature_c": temperature,
                "weather_code": wc,
                "humidity_pct": raw_humidity,
            },
        }

        faasr_log(
            f"Color palette: {base_palette_name}, hues=[{hue_min}–{hue_max}], "
            f"saturation={saturation:.2f}, brightness={brightness:.2f}, "
            f"overlay={overlay_effect}"
        )

        # -----------------------------------------------------------------------
        # 2. SHAPE DISTRIBUTION — derived from astronomical magnitudes & moon phase
        # -----------------------------------------------------------------------
        # Collect magnitude + visibility of each planet
        visible_planet_mags = []
        for name, pdata in planets.items():
            if pdata.get("is_visible"):
                mag = pdata.get("magnitude")
                if mag is not None:
                    visible_planet_mags.append((name, float(mag)))

        n_visible_planets = len(visible_planet_mags)

        # Shape weight per planet: brightest (lowest/most negative mag) → largest weight
        if visible_planet_mags:
            mag_values = np.array([m for _, m in visible_planet_mags])
            # Invert so that the most negative mag gets the highest weight
            inverted = -mag_values + float(np.max(mag_values)) + 1.0
            shape_weights = (inverted / inverted.sum()).tolist()
        else:
            shape_weights = []

        moon_phase_frac = float(moon_data.get("phase_fraction", 0.5))
        moon_illumination = float(moon_data.get("illumination_percent", 50.0))
        moon_phase_name = moon_data.get("phase_name", "Unknown")

        # Full moon → more circles; new moon → more polygons
        circle_ratio = moon_phase_frac
        polygon_ratio = 1.0 - circle_ratio

        # Number of visible constellations drives density of background micro-shapes
        n_constellations = len(visible_constellations)
        background_shape_density = float(np.clip(n_constellations / 20.0, 0.0, 1.0))

        shape_distribution = {
            "primary_shape_count": max(3, n_visible_planets + 2),
            "circle_ratio": round(circle_ratio, 4),
            "polygon_ratio": round(polygon_ratio, 4),
            "dominant_shapes": ["circle", "polygon", "line"],
            "background_shape_density": round(background_shape_density, 4),
            "visible_planets": [
                {
                    "name": name,
                    "magnitude": mag,
                    "shape_weight": round(w, 4),
                }
                for (name, mag), w in zip(visible_planet_mags, shape_weights)
            ],
            "n_visible_constellations": n_constellations,
            "source": {
                "moon_phase_name": moon_phase_name,
                "moon_illumination_pct": moon_illumination,
                "n_visible_planets": n_visible_planets,
            },
        }

        faasr_log(
            f"Shape distribution: {n_visible_planets} visible planets, "
            f"circle_ratio={circle_ratio:.2f}, polygon_ratio={polygon_ratio:.2f}, "
            f"background_density={background_shape_density:.2f}"
        )

        # -----------------------------------------------------------------------
        # 3. TEXTURE PARAMS — derived from financial volatility + wind speed
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

        # Normalise mean volatility to [0, 1]; clip at 2.0 as ceiling
        # Typical stocks: 0.2–0.5 ann. vol; crypto: 0.5–1.5+
        norm_vol = float(np.clip(mean_vol / 2.0, 0.0, 1.0))

        if norm_vol < 0.20:
            texture_type = "smooth"
            noise_frequency = 0.5
            noise_amplitude = 0.10
        elif norm_vol < 0.50:
            texture_type = "granular"
            noise_frequency = 2.0
            noise_amplitude = 0.30
        elif norm_vol < 0.75:
            texture_type = "rough"
            noise_frequency = 5.0
            noise_amplitude = 0.50
        else:
            texture_type = "chaotic"
            noise_frequency = 10.0
            noise_amplitude = 0.80

        # Stroke weight: bolder when markets are more volatile
        stroke_weight = round(float(np.clip(1.0 + max_vol * 3.0, 1.0, 10.0)), 2)

        # Directional factor from wind speed: fast wind → pronounced brush directionality
        raw_wind = float(wind_speed) if wind_speed is not None else 0.0
        wind_directional_factor = float(np.clip(raw_wind / 100.0, 0.0, 1.0))

        texture_params = {
            "texture_type": texture_type,
            "noise_frequency": round(noise_frequency, 4),
            "noise_amplitude": round(noise_amplitude, 4),
            "stroke_weight": stroke_weight,
            "wind_directional_factor": round(wind_directional_factor, 4),
            "normalized_volatility": round(norm_vol, 4),
            "source": {
                "mean_volatility_annualised": round(mean_vol, 6),
                "max_volatility_annualised": round(max_vol, 6),
                "wind_speed_kmh": raw_wind,
            },
        }

        faasr_log(
            f"Texture: type={texture_type}, noise_freq={noise_frequency}, "
            f"noise_amp={noise_amplitude}, stroke_weight={stroke_weight}, "
            f"wind_directional={wind_directional_factor:.2f}"
        )

        # -----------------------------------------------------------------------
        # 4. COMPOSITION RULES — from trend directions, moon phase, temperature
        # -----------------------------------------------------------------------
        bullish_count = sum(1 for a in assets.values() if a.get("trend") == "bullish")
        bearish_count = sum(1 for a in assets.values() if a.get("trend") == "bearish")
        total_assets = len(assets)

        bullish_ratio = bullish_count / total_assets if total_assets > 0 else 0.5

        if bullish_ratio > 0.6:
            compositional_flow = "ascending"
            movement_direction = "upward"
            energy = "expansive"
        elif (1.0 - bullish_ratio) > 0.6:
            compositional_flow = "descending"
            movement_direction = "downward"
            energy = "contracting"
        else:
            compositional_flow = "lateral"
            movement_direction = "horizontal"
            energy = "balanced"

        # Moon phase shapes the focal geometry
        if "Full Moon" in moon_phase_name:
            focal_point = "center"
            radial_symmetry = True
            layer_count = 5
        elif "New Moon" in moon_phase_name:
            focal_point = "edges"
            radial_symmetry = False
            layer_count = 3
        elif "Waxing" in moon_phase_name:
            focal_point = "upper_right"
            radial_symmetry = False
            layer_count = 4
        else:  # Waning
            focal_point = "lower_left"
            radial_symmetry = False
            layer_count = 4

        # Element density: warmer temperatures → more dense / energetic compositions
        # Scaled across the plausible range −10 °C to 50 °C
        element_density = float(np.clip(0.3 + 0.5 * (temperature + 10.0) / 60.0, 0.1, 1.0))

        asset_trends = {
            symbol: adata.get("trend", "unknown")
            for symbol, adata in assets.items()
        }

        composition_rules = {
            "compositional_flow": compositional_flow,
            "movement_direction": movement_direction,
            "energy": energy,
            "focal_point": focal_point,
            "radial_symmetry": radial_symmetry,
            "layer_count": layer_count,
            "element_density": round(element_density, 4),
            "golden_ratio_guide": True,
            "asset_trends": asset_trends,
            "source": {
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "total_assets": total_assets,
                "moon_phase_name": moon_phase_name,
                "temperature_c": temperature,
            },
        }

        faasr_log(
            f"Composition: flow={compositional_flow}, focal={focal_point}, "
            f"radial_symmetry={radial_symmetry}, layer_count={layer_count}, "
            f"element_density={element_density:.2f}"
        )

        # -----------------------------------------------------------------------
        # Assemble unified art parameter set
        # -----------------------------------------------------------------------
        art_params = {
            "color_palette": color_palette,
            "shape_distribution": shape_distribution,
            "texture_params": texture_params,
            "composition_rules": composition_rules,
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
        faasr_log(f"Art parameters uploaded to S3 folder '{folder}' as '{output1}'")

    finally:
        for tmp in [local_weather, local_astro, local_financial, local_output]:
            if os.path.exists(tmp):
                os.remove(tmp)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---