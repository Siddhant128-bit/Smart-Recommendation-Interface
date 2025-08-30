# Required packages:
# pip install pytrends pandas prophet

from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
import pandas as pd
from prophet import Prophet
from datetime import timedelta,datetime
import time

def get_google_trend(title, date_str, max_retries=5, initial_delay=10,window=10):
    """
    title: str, movie/series title
    date_str: str, format 'YYYY-MM-DD'
    returns: trend score (0-100)
    Handles TooManyRequestsError with retries and exponential backoff.
    """
    target_date = pd.to_datetime(date_str)
    pytrends = TrendReq(hl='en-US', tz=360)

    delay = initial_delay

    for attempt in range(max_retries):
        try:
            target_date = pd.to_datetime(date_str)
            start_date  = (target_date - timedelta(days=window)).strftime("%Y-%m-%d")
            end_date    = (target_date + timedelta(days=0)).strftime("%Y-%m-%d")
            #check if date is in the future 
            if target_date > datetime.now():
                time_frame="today 5-y"
            else:
                time_frame=f"{start_date} {end_date}"
            pytrends.build_payload([title], timeframe=time_frame,gprop='youtube')
            data = pytrends.interest_over_time()
            if data.empty:
                return None

            # Monthly resample
            # print(start_date,end_date)
            # print(data[title])
            # print(data[title].iloc[0])
            # print(data.loc[data['date']=='2025-08-15'])
            data_monthly = data.resample('M').mean()
            data_monthly = data_monthly.reset_index()
            data_monthly = data_monthly[['date', title]]
            data_monthly.rename(columns={'date': 'ds', title: 'y'}, inplace=True)

            if target_date <= data_monthly['ds'].max():
                # Historical value
                # closest = data_monthly.iloc[(data_monthly['ds'] - target_date).abs().argsort()[:1]]
                # return float(data[title].mean())
                return float(data[title].iloc[0])
            else:
                # Forecast
                m = Prophet(yearly_seasonality=True, daily_seasonality=False, weekly_seasonality=False)
                m.fit(data_monthly)
                future = pd.DataFrame({'ds': pd.date_range(start=data_monthly['ds'].max() + pd.offsets.MonthBegin(1),
                                                           end=target_date, freq='D')})
                forecast = m.predict(future)
                closest_forecast = forecast.iloc[(forecast['ds'] - target_date).abs().argsort()[:1]]
                return float(closest_forecast['yhat'].values[0])

        except TooManyRequestsError:
            print(f"Rate limited by Google. Waiting {delay} seconds (attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)
            delay *= 1.25  # exponential backoff
        except Exception as e:
            print(f"Error fetching trend for {title}: {e}")
            return None

    print(f"Failed to fetch trend for {title} after {max_retries} retries.")
    return None

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    title = "Nobody"
    date_str = "2025-8-16"
    time.sleep(30)
    trend_score = get_google_trend(title, date_str,initial_delay=30,window=30)

    print(f"Google Trend score for '{title}' on {date_str}: {trend_score}")
