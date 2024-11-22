import requests
import websocket
import json
import time
from datetime import datetime, timezone, timedelta
from collections import deque
import pandas as pd
import streamlit as st

# Set Streamlit configuration
st.set_page_config(page_title="Crypto Tracker", layout="wide")

# Define tokens
FUTURES_COINS = [
    "BTCUSDT", "ETHUSDT", "PONKEUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "DOGEUSDT", "TROYUSDT", "ADAUSDT", "TRXUSDT",
    "SHIBUSDT", "AVAXUSDT", "TONUSDT", "SUIUSDT", "1000PEPEUSDT",
    "LINKUSDT", "BCHUSDT", "DOTUSDT", "LEOUSDT", "NEARUSDT",
    "LTCUSDT", "APTUSDT", "XLMUSDT", "UNIUSDT", "CROUSDT",
    "ICPUSDT", "ETCUSDT", "KASUSDT", "VETUSDT", "HBARUSDT",
    "ALGOUSDT", "FILUSDT", "AAVEUSDT", "GRTUSDT", "FTMUSDT",
    "XTZUSDT", "THETAUSDT", "EGLDUSDT", "FLOWUSDT", "AXSUSDT",
    "MANAUSDT", "SANDUSDT", "CHZUSDT", "ENJUSDT", "ZILUSDT",
    "HOTUSDT", "CKBUSDT", "CELOUSDT", "ONEUSDT", "KSMUSDT",
    "QTUMUSDT", "OMGUSDT", "ZRXUSDT", "BATUSDT", "CAKEUSDT",
    "CRVUSDT", "SUSHIUSDT", "COMPUSDT", "YFIUSDT", "BALUSDT",
    "RENUSDT", "LRCUSDT", "1INCHUSDT", "SRMUSDT", "INJUSDT",
    "OCEANUSDT", "AUDIOUSDT", "RNDRUSDT", "ARUSDT", "STORJUSDT",
    "ANKRUSDT", "CVCUSDT", "FETUSDT", "IOTXUSDT", "AGIXUSDT",
    "MASKUSDT", "BANDUSDT", "OXTUSDT", "SKLUSDT", "OGNUSDT",
    "COTIUSDT", "DENTUSDT", "REQUSDT", "POWRUSDT", "SYSUSDT",
    "WANUSDT", "ARKUSDT", "MITHUSDT", "BLZUSDT", "STMXUSDT",
    "DIAUSDT", "AVAUSDT", "TRBUSDT", "KEEPUSDT", "AKROUSDT",
    "BELUSDT", "KAIUSDT", "LITUSDT", "ALPHAUSDT", "CTKUSDT",
    "DGBUSDT", "DUSKUSDT", "FLMUSDT", "GTCUSDT", "HNTUSDT",
    "ICXUSDT", "KAVAUSDT", "LINAUSDT", "MKRUSDT", "MTLUSDT",
    "NKNUSDT", "NMRUSDT", "OGUSDT", "OMUSDT", "PERLUSDT",
    "RAYUSDT", "REEFUSDT", "ROSEUSDT", "RSRUSDT", "SFPUSDT",
    "SLPUSDT", "SNXUSDT", "STMXUSDT", "SUNUSDT",
    "SXPUSDT", "TLMUSDT", "TOMOUSDT", "TRUUSDT",
    "TVKUSDT", "UMAUSDT", "UNFIUSDT", "UTKUSDT", "VITEUSDT",
    "WAVESUSDT", "WINGUSDT", "WNXMUSDT", "XEMUSDT", "XVGUSDT",
    "YFIIUSDT", "ZENUSDT", "ZRXUSDT", "CTSIUSDT", "DODOUSDT",
    "FORTHUSDT", "FRONTUSDT", "HARDUSDT", "IRISUSDT", "JSTUSDT",
    "LITUSDT", "MDAUSDT", "MDXUSDT", "NBSUSDT", "NULSUSDT",
    "POLSUSDT", "PONDUSDT", "PSGUSDT", "QNTUSDT", "RIFUSDT",
    "RLCUSDT", "SANDUSDT", "SANTOSUSDT", "SUSDUSDT", "TKOUSDT",
    "TORNUSDT", "TWTUSDT", "UFTUSDT", "VIDTUSDT", "WTCUSDT"
]

REST_FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
REST_SPOT_BASE_URL = "https://api.binance.com/api/v3/klines"
WS_FUTURES_BASE_URL = "wss://fstream.binance.com/ws"
WS_SPOT_BASE_URL = "wss://stream.binance.com:9443/ws"
TIMEFRAMES = {"1h": 3600, "2h": 7200, "4h": 14400, "48h": 172800}

# Store data
historical_data = {coin: deque(maxlen=2000) for coin in FUTURES_COINS}
latest_prices = {coin: None for coin in FUTURES_COINS}

# Fetch historical data
def fetch_historical_data(symbol, interval="1h", limit=200):
    try:
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = requests.get(REST_FUTURES_BASE_URL, params=params)
        if response.status_code != 200:
            response = requests.get(REST_SPOT_BASE_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            return [(datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc), float(item[4])) for item in data]
        else:
            print(f"Error fetching historical data for {symbol}: {response.status_code}, {response.text}")
            return []
    except Exception as e:
        print(f"Exception during historical data fetch for {symbol}: {e}")
        return []

# Initialize historical data
def initialize_historical_data():
    for coin in FUTURES_COINS:
        data_1h = fetch_historical_data(coin, interval="1h", limit=200)
        if data_1h:
            historical_data[coin].extend(data_1h)
        time.sleep(0.1)

# WebSocket message handler
def on_message(ws, message, market_type="futures"):
    global latest_prices, historical_data
    try:
        data = json.loads(message)
        coin = data['s'].upper()
        if coin in latest_prices:
            close_price = float(data['c'])
            timestamp = datetime.now(tz=timezone.utc)
            latest_prices[coin] = close_price
            historical_data[coin].append((timestamp, close_price))
    except Exception as e:
        print(f"Error processing WebSocket message ({market_type}): {e}")

def connect_websocket():
    while True:
        try:
            futures_streams = [f"{coin.lower()}@ticker" for coin in FUTURES_COINS]
            spot_streams = [f"{coin.lower()}@ticker" for coin in FUTURES_COINS]

            def on_message_wrapper(ws, message, market_type="futures"):
                on_message(ws, message, market_type)

            futures_ws_url = f"{WS_FUTURES_BASE_URL}/{'/'.join(futures_streams)}"
            futures_ws = websocket.WebSocketApp(
                futures_ws_url,
                on_message=lambda ws, msg: on_message_wrapper(ws, msg, "futures")
            )

            spot_ws_url = f"{WS_SPOT_BASE_URL}/{'/'.join(spot_streams)}"
            spot_ws = websocket.WebSocketApp(
                spot_ws_url,
                on_message=lambda ws, msg: on_message_wrapper(ws, msg, "spot")
            )

            import threading
            threading.Thread(target=futures_ws.run_forever, daemon=True).start()
            threading.Thread(target=spot_ws.run_forever, daemon=True).start()
            break
        except Exception as e:
            print(f"WebSocket connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def calculate_changes(coin):
    changes = {}
    now = datetime.now(tz=timezone.utc)

    if latest_prices[coin] is None:
        return {label: None for label in TIMEFRAMES}

    prices_snapshot = list(historical_data[coin])

    for label, seconds in TIMEFRAMES.items():
        target_time = now - timedelta(seconds=seconds)
        oldest_price = None

        for ts, price in reversed(prices_snapshot):
            if ts <= target_time:
                oldest_price = price
                break

        if oldest_price is not None and latest_prices[coin] is not None:
            changes[label] = ((latest_prices[coin] - oldest_price) / oldest_price) * 100
        else:
            changes[label] = None

    return changes

# Main Streamlit app

def main():
    st.title("Crypto Tracker with Live Updates")
    st.write("Track real-time percentage changes across multiple timeframes.")

    # Initialize historical data
    st.write("Initializing historical data...")
    initialize_historical_data()

    # Start WebSocket in a separate thread
    connect_websocket()

    # Create a placeholder for the table
    table_placeholder = st.empty()

    # Continuously update the table
    while True:
        table_data = []
        for coin in FUTURES_COINS:
            changes = calculate_changes(coin)
            table_data.append({
                "Symbol": coin.upper(),
                "1h %": changes["1h"] if changes["1h"] is not None else "N/A",
                "2h %": changes["2h"] if changes["2h"] is not None else "N/A",
                "4h %": changes["4h"] if changes["4h"] is not None else "N/A",
                "48h %": changes["48h"] if changes["48h"] is not None else "N/A",
                "Latest Price": f"${latest_prices[coin]:.6f}" if latest_prices[coin] is not None else "N/A"
            })

        # Convert to DataFrame
        df = pd.DataFrame(table_data)

        # Highlight and color logic
        def format_percentage(value, positive_threshold, negative_threshold):
            if isinstance(value, (int, float)):
                circle = "🟢" if value >= 0 else "🔴"
                if value > positive_threshold:
                    highlight = "✅"
                elif value < negative_threshold:
                    highlight = "❌"
                else:
                    highlight = ""  # Nothing if conditions aren't met
                return f"{circle} {value:.2f}% {highlight}".strip()
            return "N/A"

        # Apply formatting for each timeframe
        df["1h %"] = df["1h %"].apply(
            lambda x: format_percentage(x, 5, -5) if x != "N/A" else x
        )
        df["2h %"] = df["2h %"].apply(
            lambda x: format_percentage(x, 10, -10) if x != "N/A" else x
        )
        df["4h %"] = df["4h %"].apply(
            lambda x: format_percentage(x, 15, -15) if x != "N/A" else x
        )
        df["48h %"] = df["48h %"].apply(
            lambda x: format_percentage(x, 20, -20) if x != "N/A" else x
        )

        # Display in Streamlit with sorting enabled
        table_placeholder.dataframe(df, use_container_width=True, height=800)

        time.sleep(1)  # Refresh every second


if __name__ == "__main__":
    main()