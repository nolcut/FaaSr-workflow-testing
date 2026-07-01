import datetime
import json
import os

import numpy as np
import requests
import yfinance as yf


# --- CONTRACT HELPERS ---
def _faasr_promises(folder):
    if "financial_data.json" not in [_k.rsplit("/", 1)[-1] for _k in faasr_get_folder_list(prefix=folder)]:
        faasr_log("[PROMISE] CONTRACT VIOLATION: Financial data JSON file was not uploaded to S3 after fetching from Yahoo Finance and CoinGecko")
        raise SystemExit(1)
# --- end contract helpers ---


def fetch_financial_data(folder: str, output1: str) -> None:
    """
    Fetches recent price data for representative assets (major stocks and
    cryptocurrencies) from Yahoo Finance and CoinGecko. Computes summary
    statistics including closing prices, daily returns, volatility, and trend
    direction. Saves results as a JSON file to S3.
    """
    faasr_log("Starting financial data fetch from Yahoo Finance and CoinGecko")

    assets = {}

    # ------------------------------------------------------------------
    # Yahoo Finance — major stocks (via yfinance, no API key required)
    # ------------------------------------------------------------------
    stock_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "META"]

    for symbol in stock_symbols:
        faasr_log(f"Fetching Yahoo Finance data for {symbol}")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="30d")

        if hist.empty:
            msg = f"Yahoo Finance returned no price data for {symbol}"
            faasr_log(msg)
            raise RuntimeError(msg)

        dates = [str(d.date()) for d in hist.index]
        close_prices = hist["Close"].tolist()
        close_arr = np.array(close_prices)

        # Daily returns: (P_t - P_{t-1}) / P_{t-1}
        daily_returns = np.diff(close_arr) / close_arr[:-1]

        # Annualised volatility (252 trading days for stocks)
        volatility = float(np.std(daily_returns) * np.sqrt(252))

        # Trend: compare last close to first close in the window
        trend = "bullish" if float(close_arr[-1]) > float(close_arr[0]) else "bearish"

        assets[symbol] = {
            "type": "stock",
            "dates": dates,
            "close_prices": [round(float(p), 4) for p in close_prices],
            "daily_returns": [round(float(r), 6) for r in daily_returns],
            "current_price": round(float(close_arr[-1]), 4),
            "volatility_annualised": round(volatility, 6),
            "trend": trend,
        }

        faasr_log(
            f"{symbol}: current={float(close_arr[-1]):.2f}, "
            f"volatility={volatility:.4f}, trend={trend}"
        )

    # ------------------------------------------------------------------
    # CoinGecko — major cryptocurrencies (free public API, no key required)
    # ------------------------------------------------------------------
    crypto_ids = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
    }

    cg_base = "https://api.coingecko.com/api/v3"

    for symbol, cg_id in crypto_ids.items():
        faasr_log(f"Fetching CoinGecko data for {symbol} ({cg_id})")
        url = f"{cg_base}/coins/{cg_id}/market_chart"
        params = {"vs_currency": "usd", "days": "30", "interval": "daily"}
        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            msg = (
                f"CoinGecko API error for {symbol} ({cg_id}): "
                f"HTTP {response.status_code} — {response.text[:300]}"
            )
            faasr_log(msg)
            raise RuntimeError(msg)

        data = response.json()
        price_points = data.get("prices", [])

        if not price_points:
            msg = f"CoinGecko returned no price data for {symbol} ({cg_id})"
            faasr_log(msg)
            raise RuntimeError(msg)

        dates = [
            str(datetime.datetime.utcfromtimestamp(pt[0] / 1000.0).date())
            for pt in price_points
        ]
        close_prices = [pt[1] for pt in price_points]
        close_arr = np.array(close_prices)

        # Daily returns
        daily_returns = np.diff(close_arr) / close_arr[:-1]

        # Annualised volatility (365 days for crypto — trades every day)
        volatility = float(np.std(daily_returns) * np.sqrt(365))

        # Trend
        trend = "bullish" if float(close_arr[-1]) > float(close_arr[0]) else "bearish"

        assets[symbol] = {
            "type": "crypto",
            "dates": dates,
            "close_prices": [round(float(p), 4) for p in close_prices],
            "daily_returns": [round(float(r), 6) for r in daily_returns],
            "current_price": round(float(close_arr[-1]), 4),
            "volatility_annualised": round(volatility, 6),
            "trend": trend,
        }

        faasr_log(
            f"{symbol}: current={float(close_arr[-1]):.2f}, "
            f"volatility={volatility:.4f}, trend={trend}"
        )

    # ------------------------------------------------------------------
    # Compile result and upload to S3
    # ------------------------------------------------------------------
    financial_data = {
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "assets": assets,
    }

    local_file = "financial_data_local.json"
    try:
        with open(local_file, "w") as f:
            json.dump(financial_data, f, indent=2)

        faasr_put_file(local_file=local_file, remote_folder=folder, remote_file=output1)
        faasr_log(f"Financial data uploaded to S3 folder '{folder}' as '{output1}'")
    finally:
        if os.path.exists(local_file):
            os.remove(local_file)
    # --- CONTRACT: promises ---
    _faasr_promises(folder)
    # --- end promises ---