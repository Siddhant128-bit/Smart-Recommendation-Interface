import random
import time
import pandas as pd
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
from prophet import Prophet

# -----------------------------
# List of proxies (format: "ip:port" with authentication)
# -----------------------------
proxies_list = [
    "http://yvnpobbd:8m2ppsopiwfv@136.0.207.84:6661",    # 🇺🇸 Orem
    "http://yvnpobbd:8m2ppsopiwfv@64.137.96.74:6641",    # 🇪🇸 Madrid
    "http://yvnpobbd:8m2ppsopiwfv@45.38.107.97:6014",    # 🇬🇧 London
    "http://yvnpobbd:8m2ppsopiwfv@198.23.239.134:6540",   # 🇺🇸 Buffalo
    "http://yvnpobbd:8m2ppsopiwfv@107.172.163.27:6543",  # 🇺🇸 Bloomingdale
    "http://yvnpobbd:8m2ppsopiwfv@45.43.186.39:6257",    # 🇪🇸 Madrid
    "http://yvnpobbd:8m2ppsopiwfv@154.203.43.247:5536",  # 🇯🇵 Chiyoda City
    "http://yvnpobbd:8m2ppsopiwfv@84.247.60.125:6095",   # 🇵🇱 Warsaw
    "http://yvnpobbd:8m2ppsopiwfv@216.10.27.159:6837",   # 🇺🇸 Dallas
    "http://yvnpobbd:8m2ppsopiwfv@142.147.128.93:6593"   # 🇺🇸 Orem
]


# -----------------------------
# Function to get Google Trends
# -----------------------------
def get_google_trend(title, target_date_str, window=30, max_retries=5, initial_delay=10):
    target_date = pd.to_datetime(target_date_str)
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            # pick a random proxy each attempt
            if attempt>len(proxies_list):
                try_element=attempt%proxies_list
            else:
                try_element=attempt
            print(f'Trial Proxy: {proxies_list[try_element]}')
            
            pytrends = TrendReq(hl='en-US', tz=360, proxies=[proxies_list[try_element]])

            today = datetime.now()
            start_date = (today - timedelta(days=window)).strftime("%Y-%m-%d")
            end_date   = today.strftime("%Y-%m-%d")

            # Google Trends timeframe
            time_frame = f"{start_date} {end_date}"
            pytrends.build_payload([title], timeframe=time_frame, gprop='youtube')
            data = pytrends.interest_over_time()

            if data.empty:
                return None

            # Keep only daily values
            data = data[[title]]
            data = data.reset_index().rename(columns={"date": "ds", title: "y"})

            last_date = data['ds'].max()

            # If target date is within historical data
            if target_date <= last_date:
                closest = data.iloc[(data['ds'] - target_date).abs().argsort()[:1]]
                return float(closest['y'].values[0])

            # Otherwise forecast forward
            m = Prophet(
                growth="logistic",
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False
            )
            data['cap'] = 100
            data['floor'] = 0

            m.fit(data)

            future = pd.DataFrame({
                'ds': pd.date_range(start=last_date + timedelta(days=1),
                                    end=target_date,
                                    freq='D')
            })
            future['cap'] = 100
            future['floor'] = 0

            forecast = m.predict(future)
            closest_forecast = forecast.iloc[(forecast['ds'] - target_date).abs().argsort()[:1]]
            yhat = float(closest_forecast['yhat'].values[0])

            # Clip to [0,100]
            return max(0, min(100, yhat))

        except TooManyRequestsError:
            print(f"Rate limited by Google. Waiting {delay} seconds (attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
        except Exception as e:
            print(f"Error fetching trend for {title}: {e}")
            return None

    print(f"Failed to fetch trend for {title} after {max_retries} retries.")
    return None

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    title = "Children of Men"
    date_str = "2025-09-07"

    trend_score = get_google_trend(title, date_str, initial_delay=1,max_retries=30, window=180)

    print(f"Google Trend score for '{title}' on {date_str}: {trend_score}")
