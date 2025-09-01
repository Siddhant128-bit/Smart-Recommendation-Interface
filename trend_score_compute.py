# Required packages:
# pip install pytrends pandas prophet

from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
import pandas as pd
from prophet import Prophet
from datetime import timedelta,datetime
import time

import pandas as pd
import time
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
from prophet import Prophet

def get_google_trend(title, target_date_str, window=30, max_retries=5, initial_delay=10):
    """
    Get Google Trends score (0-100) for a given title and target date.
    Uses history from [today - window, today] as base, then forecasts forward if needed.

    Parameters
    ----------
    title : str
        Movie/series keyword
    target_date_str : str
        Date string 'YYYY-MM-DD'
    window : int
        Days of history to use from today backwards
    max_retries : int
        Retry count if rate limited
    initial_delay : int
        Initial wait before retry (seconds)

    Returns
    -------
    float or None
        Trend score (0-100), or None if data unavailable
    """
    target_date = pd.to_datetime(target_date_str)
    pytrends = TrendReq(hl='en-US', tz=360)

    delay = initial_delay

    for attempt in range(max_retries):
        try:
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

            # Add cap/floor to bound forecasts
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
            print(f'Trend Score obtained from forecast is {yhat}')
            # Clip to [0,100]
            return max(0, min(100, yhat))

        except TooManyRequestsError:
            print(f"Rate limited by Google. Waiting {delay} seconds (attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
            delay *= 1.5  # backoff
        except Exception as e:
            print(f"Error fetching trend for {title}: {e}")
            return None

    print(f"Failed to fetch trend for {title} after {max_retries} retries.")
    return None


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    title = "Schindler's List"
    date_str = "2025-09-07"
    time.sleep(30)
    trend_score = get_google_trend(title, date_str,initial_delay=30,window=180)

    print(f"Google Trend score for '{title}' on {date_str}: {trend_score}")
