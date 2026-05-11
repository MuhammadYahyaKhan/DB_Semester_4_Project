import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.io import to_html



def calculate_metrics(df):
    
    df['Cumulative_Return'] = (1 + df['Strategy_Return']).cumprod()
    total_return = (df['Cumulative_Return'].iloc[-1] - 1) * 100 if not df.empty else 0
    
    
    df['Peak'] = df['Cumulative_Return'].cummax()
    df['Drawdown'] = (df['Cumulative_Return'] - df['Peak']) / df['Peak']
    max_drawdown = df['Drawdown'].min() * 100 if not df.empty else 0
    
    
    trade_signals = df['Signal'].diff().fillna(0)
    total_trades = (trade_signals == 1).sum()
    
    return float(round(total_return, 2)), float(round(max_drawdown, 2)), int(total_trades)

def generate_chart(df, traces, title):
    
    fig = go.Figure()
    
    
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Close Price', line=dict(color='#94a3b8', width=1.5)))
    
    
    for trace in traces:
        fig.add_trace(trace)
        
    fig.update_layout(
        title=title,
        paper_bgcolor='#0f172a',
        plot_bgcolor='#0f172a',
        font=dict(color='#cbd5e1'),
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=True, gridcolor='#334155'),
        yaxis=dict(showgrid=True, gridcolor='#334155'),
        hovermode='x unified'
    )
    
    return to_html(fig, full_html=False)


def run_ma_crossover(df, short_window, long_window):
    
    df['SMA_Short'] = df['Close'].rolling(window=short_window).mean()
    df['SMA_Long'] = df['Close'].rolling(window=long_window).mean()
    
    
    df['Signal'] = np.where(df['SMA_Short'] > df['SMA_Long'], 1, 0)
    
    
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal'].shift(1).fillna(0)
    df = df.dropna()
    
    tot_ret, max_dd, trades = calculate_metrics(df)
    
    # Visuals
    traces = [
        go.Scatter(x=df.index, y=df['SMA_Short'], name=f'{short_window} SMA', line=dict(color='#38bdf8', width=2)),
        go.Scatter(x=df.index, y=df['SMA_Long'], name=f'{long_window} SMA', line=dict(color='#f472b6', width=2))
    ]
    chart = generate_chart(df, traces, "Moving Average Crossover")
    
    return tot_ret, max_dd, trades, chart, df


def run_rsi_mean_reversion(df, window, overbought, oversold):
    """Strategy 2: RSI Mean Reversion"""
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
  
    df['Signal'] = np.nan
    df.loc[df['RSI'] < oversold, 'Signal'] = 1
    df.loc[df['RSI'] > overbought, 'Signal'] = 0
    df['Signal'] = df['Signal'].ffill().fillna(0) # Hold position until opposite signal
    
    df['Market_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal'].shift(1).fillna(0)
    df = df.dropna()
    
    tot_ret, max_dd, trades = calculate_metrics(df)
    
    # Visuals: For RSI, we plot price but highlight buy zones
    traces = [] # Just keeping the chart simple with price for now, as RSI is technically an oscillator below the chart
    chart = generate_chart(df, traces, f"RSI Tracking (Window: {window})")
    
    return tot_ret, max_dd, trades, chart, df


def run_macd_momentum(df, fast_ema, slow_ema, signal_line):
    """Strategy 3: MACD Momentum"""
    
    close_price = df['Close'].squeeze()
    
    
    df['EMA_Fast'] = close_price.ewm(span=fast_ema, adjust=False).mean()
    df['EMA_Slow'] = close_price.ewm(span=slow_ema, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['Signal_Line'] = df['MACD'].ewm(span=signal_line, adjust=False).mean()
    
    
    df['Signal'] = np.nan
    
    buy_mask = (df['MACD'] > df['Signal_Line']).squeeze()
    sell_mask = (df['MACD'] < df['Signal_Line']).squeeze()
    
    df.loc[buy_mask, 'Signal'] = 1
    df.loc[sell_mask, 'Signal'] = 0
    df['Signal'] = df['Signal'].ffill().fillna(0)
    
    
    df['Market_Return'] = close_price.pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal'].shift(1).fillna(0)
    df = df.dropna()
    
    tot_ret, max_dd, trades = calculate_metrics(df)
    
    import plotly.graph_objs as go
    
    traces = [
        go.Scatter(x=df.index, y=df['MACD'].squeeze(), name='MACD', line=dict(color='#3b82f6')),
        go.Scatter(x=df.index, y=df['Signal_Line'].squeeze(), name='Signal', line=dict(color='#ef4444'))
    ]
    chart = generate_chart(df, traces, "MACD Momentum")
    
    return tot_ret, max_dd, trades, chart, df



def run_bollinger_bands(df, sma_window, std_dev):
    """Strategy 4: Bollinger Bands Volatility"""
    
    close_price = df['Close'].squeeze()
    
    
    df['SMA'] = close_price.rolling(window=sma_window).mean()
    df['STD'] = close_price.rolling(window=sma_window).std()
    df['Upper_Band'] = df['SMA'] + (df['STD'] * std_dev)
    df['Lower_Band'] = df['SMA'] - (df['STD'] * std_dev)
    
    # Logic: Buy on lower band touch, Sell on upper band touch
    df['Signal'] = np.nan
    
    # Fix: Squeeze the boolean masks to ensure they are 1D for .loc
    buy_mask = (close_price < df['Lower_Band']).squeeze()
    sell_mask = (close_price > df['Upper_Band']).squeeze()
    
    df.loc[buy_mask, 'Signal'] = 1
    df.loc[sell_mask, 'Signal'] = 0
    df['Signal'] = df['Signal'].ffill().fillna(0)
    
    df['Market_Return'] = close_price.pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal'].shift(1).fillna(0)
    df = df.dropna()
    
    tot_ret, max_dd, trades = calculate_metrics(df)
    
    # Visuals
    traces = [
        go.Scatter(x=df.index, y=df['Upper_Band'].squeeze(), name='Upper Band', line=dict(color='#64748b', dash='dash')),
        go.Scatter(x=df.index, y=df['Lower_Band'].squeeze(), name='Lower Band', line=dict(color='#64748b', dash='dash')),
        go.Scatter(x=df.index, y=df['SMA'].squeeze(), name='Basis (SMA)', line=dict(color='#eab308', width=1))
    ]
    chart = generate_chart(df, traces, "Bollinger Bands Reversion")
    
    return tot_ret, max_dd, trades, chart, df


def run_vwap_execution(df):
    """Strategy 5: VWAP Execution"""
    
    close_price = df['Close'].squeeze()
    high_price = df['High'].squeeze()
    low_price = df['Low'].squeeze()
    volume = df['Volume'].squeeze()
    
    
    typical_price = (high_price + low_price + close_price) / 3
    df['VWAP'] = (typical_price * volume).cumsum() / volume.cumsum()
    
    
    df['Signal'] = np.nan
    
    buy_mask = (close_price > df['VWAP']).squeeze()
    sell_mask = (close_price < df['VWAP']).squeeze()
    
    df.loc[buy_mask, 'Signal'] = 1
    df.loc[sell_mask, 'Signal'] = 0
    df['Signal'] = df['Signal'].ffill().fillna(0)
    
    # Returns
    df['Market_Return'] = close_price.pct_change()
    df['Strategy_Return'] = df['Market_Return'] * df['Signal'].shift(1).fillna(0)
    df = df.dropna()
    
    tot_ret, max_dd, trades = calculate_metrics(df)
    
    import plotly.graph_objs as go
    traces = [
        go.Scatter(x=df.index, y=df['VWAP'].squeeze(), name='VWAP', line=dict(color='#eab308', width=2))
    ]
    chart = generate_chart(df, traces, "VWAP Trend Execution")
    
    return tot_ret, max_dd, trades, chart, df