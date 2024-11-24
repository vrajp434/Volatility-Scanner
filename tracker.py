import yagmail
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
    "LINKUSDT", "BCHUSDT", "DOTUSDT", "NEARUSDT", "LTCUSDT",
    "APTUSDT", "XLMUSDT", "UNIUSDT", "ICPUSDT", "ETCUSDT",
    "KASUSDT", "VETUSDT", "HBARUSDT", "ALGOUSDT", "FILUSDT",
    "AAVEUSDT", "GRTUSDT", "FTMUSDT", "XTZUSDT", "THETAUSDT",
    "EGLDUSDT", "FLOWUSDT", "AXSUSDT", "MANAUSDT", "SANDUSDT",
    "CHZUSDT", "ENJUSDT", "ZILUSDT", "HOTUSDT", "CKBUSDT",
    "CELOUSDT", "ONEUSDT", "KSMUSDT", "QTUMUSDT",
    "ZRXUSDT", "BATUSDT", "CAKEUSDT", "CRVUSDT", "SUSHIUSDT",
    "COMPUSDT", "YFIUSDT", "BALUSDT", "RENUSDT", "LRCUSDT",
    "1INCHUSDT", "INJUSDT", "AUDIOUSDT", "STORJUSDT", "ANKRUSDT",
    "CVCUSDT", "FETUSDT", "IOTXUSDT", "MASKUSDT", "BANDUSDT",
    "OXTUSDT", "SKLUSDT", "OGNUSDT", "COTIUSDT", "DENTUSDT",
    "REQUSDT", "POWRUSDT", "SYSUSDT", "WANUSDT", "ARKUSDT",
    "DIAUSDT", "AVAUSDT", "TRBUSDT", "AKROUSDT", "BELUSDT",
    "ALPHAUSDT", "CTKUSDT", "DGBUSDT", "DUSKUSDT", "GTCUSDT",
    "ICXUSDT", "KAVAUSDT", "LINAUSDT", "MKRUSDT", "NKNUSDT",
    "NMRUSDT", "OGUSDT", "OMUSDT", "RAYUSDT",
    "ROSEUSDT", "RSRUSDT", "SFPUSDT", "SLPUSDT", "SNXUSDT",
    "STMXUSDT", "SUNUSDT", "SXPUSDT", "TLMUSDT", "UTKUSDT",
    "VITEUSDT", "XVGUSDT", "ZRXUSDT", "CTSIUSDT",
    "DODOUSDT", "FORTHUSDT", "HARDUSDT", "IRISUSDT", "JSTUSDT",
    "NULSUSDT", "PONDUSDT", "PSGUSDT", "QNTUSDT", "RIFUSDT",
    "RLCUSDT", "SANDUSDT", "SANTOSUSDT", "TKOUSDT", "TWTUSDT",
    "UFTUSDT", "VIDTUSDT"
]

REST_FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
REST_SPOT_BASE_URL = "https://api.binance.com/api/v3/klines"
WS_FUTURES_BASE_URL = "wss://fstream.binance.com/ws"
WS_SPOT_BASE_URL = "wss://stream.binance.com:9443/ws"
TIMEFRAMES = {"1h": 3600, "2h": 7200, "4h": 14400, "48h": 172800}

# Store data
historical_data = {coin: deque(maxlen=2000) for coin in FUTURES_COINS}
latest_prices = {coin: None for coin in FUTURES_COINS}
source_market = {coin: "Unknown" for coin in FUTURES_COINS}  # Track Spot or Futures

# Email setup
SENDER_EMAIL = "volatilecrypto4@gmail.com"  # Sender email (used for authentication)
RECEIVER_EMAIL = "volatilecrypto907@gmail.com"  # Receiver email (can be different)
yag = yagmail.SMTP(SENDER_EMAIL)

# Dictionary to track the last email sent time for each coin
last_email_sent_time = {}

def send_email(coin, trend):
    """Send email notifications."""
    global last_email_sent_time
    current_time = time.time()
    
    # Check if an email was sent for this coin within the last 60 seconds
    if coin in last_email_sent_time and current_time - last_email_sent_time[coin] < 60:
        return  # Skip sending email
    
    subject = f"{coin} is in a {'bullish' if trend == 'bullish' else 'bearish'} run!"
    body = (
        f"The coin {coin} met all 4 conditions for a {trend} run.\n\n"
        f"Monitor its performance closely."
    )
    try:
        # Send email to the receiver
        yag.send(to=RECEIVER_EMAIL, subject=subject, contents=body)
        print(f"Email sent to {RECEIVER_EMAIL} for {coin}: {trend}")
        last_email_sent_time[coin] = current_time  # Update the last email sent time
    except Exception as e:
        print(f"Failed to send email for {coin}: {e}")


# Fetch historical data
def fetch_historical_data(symbol, interval="1h", limit=200):
    try:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(REST_SPOT_BASE_URL, params=params)  # Spot first
        if response.status_code != 200:  # If Spot fails, use Futures
            response = requests.get(REST_FUTURES_BASE_URL, params=params)
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
def on_message(ws, message, market_type="Spot"):
    global latest_prices, historical_data, source_market
    try:
        data = json.loads(message)
        coin = data['s'].upper()
        if coin in latest_prices:
            close_price = float(data['c'])
            timestamp = datetime.now(tz=timezone.utc)
            latest_prices[coin] = close_price
            historical_data[coin].append((timestamp, close_price))
            if source_market[coin] != "Spot":  # Avoid overwriting Spot with Futures
                source_market[coin] = "Spot" if market_type == "Spot" else "Futures"
    except Exception as e:
        print(f"Error processing WebSocket message ({market_type}): {e}")

def connect_websocket():
    while True:
        try:
            futures_streams = [f"{coin.lower()}@ticker" for coin in FUTURES_COINS]
            spot_streams = [f"{coin.lower()}@ticker" for coin in FUTURES_COINS]

            def on_message_wrapper(ws, message, market_type="Spot"):
                on_message(ws, message, market_type)

            futures_ws_url = f"{WS_FUTURES_BASE_URL}/{'/'.join(futures_streams)}"
            futures_ws = websocket.WebSocketApp(
                futures_ws_url,
                on_message=lambda ws, msg: on_message_wrapper(ws, msg, "Futures")
            )

            spot_ws_url = f"{WS_SPOT_BASE_URL}/{'/'.join(spot_streams)}"
            spot_ws = websocket.WebSocketApp(
                spot_ws_url,
                on_message=lambda ws, msg: on_message_wrapper(ws, msg, "Spot")
            )

            import threading
            threading.Thread(target=futures_ws.run_forever, daemon=True).start()
            threading.Thread(target=spot_ws.run_forever, daemon=True).start()
            break
        except Exception as e:
            print(f"WebSocket connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# Calculate changes
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
    st.title("Volatility Scanner")
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
                "Latest Price": f"${latest_prices[coin]:.6f}" if latest_prices[coin] is not None else "N/A",
                "Source": source_market[coin]
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
                    highlight = ""
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

        # Check conditions and send email if criteria are met
        for index, row in df.iterrows():
            conditions_met_positive = all("✅" in str(row[timeframe]) for timeframe in ["1h %", "2h %", "4h %", "48h %"])
            conditions_met_negative = all("❌" in str(row[timeframe]) for timeframe in ["1h %", "2h %", "4h %", "48h %"])
            if conditions_met_positive:
                send_email(row["Symbol"], "bullish")
            elif conditions_met_negative:
                send_email(row["Symbol"], "bearish")

        # Display in Streamlit with sorting enabled
        table_placeholder.dataframe(df, use_container_width=True, height=800)

        time.sleep(1)  # Refresh every second


if __name__ == "__main__":
    main()