import time
import pandas as pd
from datetime import datetime, timedelta
from prophet import Prophet

# -----------------------------
# List of proxies (format: "ip:port" with authentication)
# -----------------------------


# -----------------------------
# Function to get Google Trends
# -----------------------------
def get_google_trend(title,target_date_str, data_csv):
    target_date = pd.to_datetime(target_date_str)


    data = pd.DataFrame()
    data['ds'] = pd.to_datetime(data_csv.iloc[:, 0], errors='coerce', format='%Y-%m-%d')  # Day column
    data['y']  = data_csv.iloc[:, 1]  # Dynamic trend column (e.g., 'Troy: (Worldwide)')

    print(data)
    last_date = pd.to_datetime(data['ds'].max())
    print(type(target_date),type(last_date))
    # If target date is within historical data
    if target_date <= last_date:
        closest = data.iloc[(data['ds'] - target_date).abs().argsort()[:1]]
        return float(closest['y'].values[0])
    else:
        # Otherwise forecast forward
        m = Prophet(
            growth="logistic",
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False
        )
        print("is it working till  here 2")
    
        data['cap'] = 100
        data['floor'] = 0

        m.fit(data)
        print("is it working till  here 3")
    
        future = pd.DataFrame({
            'ds': pd.date_range(start=last_date + timedelta(days=1),
                                end=target_date,
                                freq='D')
        })
        future['cap'] = 100
        future['floor'] = 0
        print("is it working till  here 4")
    
        forecast = m.predict(future)
        closest_forecast = forecast.iloc[(forecast['ds'] - target_date).abs().argsort()[:1]]
        yhat = float(closest_forecast['yhat'].values[0])
    
        print("is it working till  here 5")
    
        return max(0, min(100, yhat))

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    title = "Children of Men"
    date_str = "2025-09-07"

    trend_score = get_google_trend(title, date_str, initial_delay=1,max_retries=30, window=180)

    print(f"Google Trend score for '{title}' on {date_str}: {trend_score}")