import yfinance as yf
import pandas as pd
from datetime import date
from .models import Asset, MarketData

def update_current_market_data(ticker_symbol):
    
    ticker_symbol = ticker_symbol.upper()
    ticker_data = yf.Ticker(ticker_symbol)
    
    
    asset_name = ticker_data.info.get('shortName', ticker_symbol)
    asset_obj, created = Asset.objects.get_or_create(
        ticker=ticker_symbol,
        defaults={'name': asset_name}
    )

    
    df_history = ticker_data.history(period="1y")
    
    if df_history.empty:
        print(f"Failed to fetch data for {ticker_symbol}")
        return False

    
    MarketData.objects.filter(asset=asset_obj).delete()
    
    market_data_objs = []
    for date_idx, row in df_history.iterrows():
        market_data_objs.append(MarketData(
            asset=asset_obj,
            date=date_idx.date(),
            close_price=float(row['Close']),
            volume=int(row['Volume'])
        ))
        
    MarketData.objects.bulk_create(market_data_objs)
    
    latest_date = df_history.index[-1].date()
    latest_close = float(df_history['Close'].iloc[-1])
    print(f"Database updated: 1y data for {ticker_symbol} ending on {latest_date} | Close: ${latest_close:.2f}")
    return True


def get_historical_data_for_math(ticker_symbol, start_date, end_date):
    
    print(f"Fetching historical RAM data for {ticker_symbol}...")
    df = yf.download(ticker_symbol.upper(), start=start_date, end=end_date)
    
    if df.empty:
        return None
        
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    return df