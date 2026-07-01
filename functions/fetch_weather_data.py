import json
import os
import requests


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "weather_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Weather data JSON file was not uploaded to S3 after fetching from Open-Meteo API")
        raise SystemExit(1)
# --- end contract helpers ---


def fetch_weather_data(folder: str, output1: str) -> None:
    """
    Fetches current weather data from the Open-Meteo public API (no API key required)
    for a representative location (New York City). Retrieves temperature, wind speed,
    humidity, and weather condition code, then saves the result to S3 as JSON.
    """

    # Representative location: New York City
    latitude = 40.7128
    longitude = -74.0060

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
    }

    faasr_log(f"Fetching weather data from Open-Meteo for lat={latitude}, lon={longitude}")

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        msg = f"Open-Meteo API error: HTTP {response.status_code} — {response.text}"
        faasr_log(msg)
        raise RuntimeError(msg)

    data = response.json()

    current = data.get("current", {})
    current_units = data.get("current_units", {})

    if not current:
        msg = "Open-Meteo API returned no 'current' block in the response"
        faasr_log(msg)
        raise RuntimeError(msg)

    weather = {
        "temperature": current.get("temperature_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "humidity": current.get("relative_humidity_2m"),
        "weather_code": current.get("weather_code"),
        "latitude": latitude,
        "longitude": longitude,
        "time": current.get("time"),
        "units": {
            "temperature": current_units.get("temperature_2m", "°C"),
            "wind_speed": current_units.get("wind_speed_10m", "km/h"),
            "humidity": current_units.get("relative_humidity_2m", "%"),
        },
    }

    faasr_log(
        f"Weather data retrieved: temp={weather['temperature']}{weather['units']['temperature']}, "
        f"wind={weather['wind_speed']}{weather['units']['wind_speed']}, "
        f"humidity={weather['humidity']}{weather['units']['humidity']}, "
        f"weather_code={weather['weather_code']}"
    )

    local_file = "weather_data_local.json"
    try:
        with open(local_file, "w") as f:
            json.dump(weather, f)

        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Weather data uploaded to S3 folder '{folder}' as '{output1}'")
    finally:
        if os.path.exists(local_file):
            os.remove(local_file)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---