from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required

from .models import TraderProfile, Asset, Strategy, Simulation, Watchlist, SavedBacktest, SimulatedTrade, EquityCurve
from .data_engine import get_historical_data_for_math, update_current_market_data
from .strategies import (
    run_ma_crossover, 
    run_rsi_mean_reversion, 
    run_macd_momentum, 
    run_bollinger_bands, 
    run_vwap_execution
)


def _populate_simulation_data(simulation, ticker, df):
    asset, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
    
    # 1. Populate EquityCurve
    equity_objs = []
    initial_balance = float(simulation.initial_balance)
    
    for date, row in df.iterrows():
        # date from pandas is usually a Timestamp. Extract standard date.
        trade_date = date.date() if hasattr(date, 'date') else date
        
        cum_ret = float(row.get('Cumulative_Return', 1.0))
        if cum_ret != cum_ret: # Check for NaN
            cum_ret = 1.0
            
        eq_val = initial_balance * cum_ret
        equity_objs.append(EquityCurve(simulation=simulation, date=trade_date, equity_value=eq_val))
    
    EquityCurve.objects.bulk_create(equity_objs)
    
    # 2. Populate SimulatedTrade
    trade_objs = []
    df['Trade_Signal'] = df['Signal'].diff().fillna(0)
    
    for date, row in df[df['Trade_Signal'] != 0].iterrows():
        signal_val = float(row['Trade_Signal'])
        if signal_val > 0:
            action = 'BUY'
        elif signal_val < 0:
            action = 'SELL'
        else:
            continue
            
        trade_date = date.date() if hasattr(date, 'date') else date
        close_price = float(row['Close'])
        cum_ret = float(row.get('Cumulative_Return', 1.0))
        if cum_ret != cum_ret:
            cum_ret = 1.0
            
        current_eq = initial_balance * cum_ret
        
        try:
            quantity = int(current_eq // close_price) if close_price > 0 else 0
        except Exception:
            quantity = 0
            
        trade_objs.append(SimulatedTrade(
            simulation=simulation,
            asset=asset,
            trade_date=trade_date,
            action=action,
            quantity=quantity,
            price=close_price
        ))
        
    if trade_objs:
        SimulatedTrade.objects.bulk_create(trade_objs)



def register_view(request):
    """Handles new user registration"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create the linked TraderProfile
            TraderProfile.objects.create(user=user, total_balance=100000.00)
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'trading/register.html', {'form': form})

def login_view(request):
    """Handles user login"""
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'trading/login.html', {'form': form})

def logout_view(request):
    """Handles user logout"""
    if request.method == 'POST':
        logout(request)
        return redirect('login')
    # Fallback for GET requests
    logout(request)
    return redirect('login')




@login_required
def dashboard(request):
    """Renders the main dashboard menu."""
    profile, _ = TraderProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        new_balance = request.POST.get('new_balance')
        if new_balance:
            profile.total_balance = new_balance
            profile.save()
            return redirect('dashboard')
            
    from django.db.models import Sum, Avg, Max, Min, Count
    
    watchlist = Watchlist.objects.filter(user=request.user)
    simulations = Simulation.objects.filter(user=request.user).order_by('-id')[:5]
    saved_backtests = SavedBacktest.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    # --- Deep Analytics ---
    user_backtests = SavedBacktest.objects.filter(user=request.user)
    
    total_backtests_run = user_backtests.count()
    
    avg_return = user_backtests.aggregate(Avg('total_return'))['total_return__avg'] or 0.0
    
    best_strategy_obj = user_backtests.order_by('-total_return').first()
    best_strategy_name = best_strategy_obj.strategy_name if best_strategy_obj else "N/A"
    best_strategy_return = best_strategy_obj.total_return if best_strategy_obj else 0.0
    
    worst_drawdown = user_backtests.aggregate(Min('max_drawdown'))['max_drawdown__min'] or 0.0
    
    total_trades_exec = user_backtests.aggregate(Sum('total_trades'))['total_trades__sum'] or 0
    
    unique_assets_tested = user_backtests.values('ticker').distinct().count()
    
    context = {
        'current_balance': profile.total_balance,
        'watchlist': watchlist,
        'simulations': simulations,
        'saved_backtests': saved_backtests,
        
        # Analytics context
        'total_backtests': total_backtests_run,
        'avg_return': avg_return,
        'best_strategy_name': best_strategy_name,
        'best_strategy_return': best_strategy_return,
        'worst_drawdown': worst_drawdown,
        'total_trades_exec': total_trades_exec,
        'unique_assets_tested': unique_assets_tested,
    }
    return render(request, 'trading/dashboard.html', context)

@login_required
def simulation_detail(request, sim_id):
    """Shows the chart and trade history for a specific backtest."""
    from django.shortcuts import get_object_or_404
    import plotly.graph_objects as go
    from plotly.io import to_html
    
    simulation = get_object_or_404(Simulation, id=sim_id, user=request.user)
    trades = SimulatedTrade.objects.filter(simulation=simulation).order_by('trade_date')
    equity_curve = EquityCurve.objects.filter(simulation=simulation).order_by('date')
    
    chart_html = ""
    if equity_curve.exists():
        dates = [ec.date for ec in equity_curve]
        values = [float(ec.equity_value) for ec in equity_curve]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=values, name='Equity', line=dict(color='#10b981', width=2)))
        fig.update_layout(
            title=f"{simulation.strategy.name} P&L",
            paper_bgcolor='#0f172a',
            plot_bgcolor='#0f172a',
            font=dict(color='#cbd5e1'),
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor='#334155'),
            yaxis=dict(showgrid=True, gridcolor='#334155'),
            hovermode='x unified'
        )
        chart_html = to_html(fig, full_html=False)
        
    context = {
        'simulation': simulation,
        'trades': trades,
        'chart_html': chart_html,
    }
    return render(request, 'trading/simulation_detail.html', context)

@login_required
def strategy1_view(request):
    """Strategy 1: Moving Average Crossover"""
    context = {}
    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        short_window = int(request.POST.get('short_window'))
        long_window = int(request.POST.get('long_window'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        context.update({'ticker': ticker, 'short_window': short_window, 'long_window': long_window, 'start_date': start_date, 'end_date': end_date})
        
        df = get_historical_data_for_math(ticker, start_date, end_date)
        update_current_market_data(ticker)
        
        if df is not None and not df.empty:
            tot_ret, max_dd, trades, chart_html, df = run_ma_crossover(df, short_window, long_window)
            
            # --- DATABASE SAVING LOGIC ---
            strategy_obj, created = Strategy.objects.get_or_create(
                name="SMA Crossover",
                defaults={'description': 'Moving average crossover momentum strategy.'}
            )
            
            sim_initial_balance = 10000.00
            sim_final_balance = sim_initial_balance * (1 + (tot_ret / 100))
            
            asset_obj, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
            
            Simulation.objects.filter(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date
            ).delete()
            
            simulation_obj = Simulation.objects.create(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date,
                initial_balance=sim_initial_balance,
                final_balance=sim_final_balance
            )
            
            _populate_simulation_data(simulation_obj, ticker, df)
            
            SavedBacktest.objects.filter(
                user=request.user,
                strategy_name="SMA Crossover",
                ticker=ticker.upper(),
                parameters=f"Short: {short_window}, Long: {long_window}"
            ).delete()
            
            SavedBacktest.objects.create(
                user=request.user,
                strategy_name="SMA Crossover",
                ticker=ticker.upper(),
                parameters=f"Short: {short_window}, Long: {long_window}",
                total_return=tot_ret,
                max_drawdown=max_dd,
                total_trades=trades
            )
            
            context.update({'backtest_run': True, 'total_return': tot_ret, 'max_drawdown': max_dd, 'total_trades': trades, 'chart_html': chart_html})
            
    return render(request, 'trading/strategy1.html', context)


@login_required
def strategy2_view(request):
    """Strategy 2: RSI Mean Reversion"""
    context = {}
    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        rsi_window = int(request.POST.get('rsi_window'))
        overbought = int(request.POST.get('overbought'))
        oversold = int(request.POST.get('oversold'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        context.update({'ticker': ticker, 'rsi_window': rsi_window, 'overbought': overbought, 'oversold': oversold, 'start_date': start_date, 'end_date': end_date})
        
        df = get_historical_data_for_math(ticker, start_date, end_date)
        update_current_market_data(ticker)
        
        if df is not None and not df.empty:
            tot_ret, max_dd, trades, chart_html, df = run_rsi_mean_reversion(df, rsi_window, overbought, oversold)
            
            # --- DATABASE SAVING LOGIC ---
            strategy_obj, created = Strategy.objects.get_or_create(
                name="RSI Mean Reversion",
                defaults={'description': 'Relative Strength Index overbought/oversold strategy.'}
            )
            
            sim_initial_balance = 10000.00
            sim_final_balance = sim_initial_balance * (1 + (tot_ret / 100))
            
            asset_obj, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
            
            Simulation.objects.filter(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date
            ).delete()
            
            simulation_obj = Simulation.objects.create(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date,
                initial_balance=sim_initial_balance,
                final_balance=sim_final_balance
            )
            
            _populate_simulation_data(simulation_obj, ticker, df)

            SavedBacktest.objects.filter(
                user=request.user,
                strategy_name="RSI Mean Reversion",
                ticker=ticker.upper(),
                parameters=f"Window: {rsi_window}, OB: {overbought}, OS: {oversold}"
            ).delete()

            SavedBacktest.objects.create(
                user=request.user,
                strategy_name="RSI Mean Reversion",
                ticker=ticker.upper(),
                parameters=f"Window: {rsi_window}, OB: {overbought}, OS: {oversold}",
                total_return=tot_ret,
                max_drawdown=max_dd,
                total_trades=trades
            )
            
            context.update({'backtest_run': True, 'total_return': tot_ret, 'max_drawdown': max_dd, 'total_trades': trades, 'chart_html': chart_html})
        else:
            context['error'] = "Could not fetch data."
            
    return render(request, 'trading/strategy2.html', context)


@login_required
def strategy3_view(request):
    """Strategy 3: MACD Momentum"""
    context = {}
    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        fast_ema = int(request.POST.get('fast_ema'))
        slow_ema = int(request.POST.get('slow_ema'))
        signal_line = int(request.POST.get('signal_line'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        context.update({'ticker': ticker, 'fast_ema': fast_ema, 'slow_ema': slow_ema, 'signal_line': signal_line, 'start_date': start_date, 'end_date': end_date})
        
        df = get_historical_data_for_math(ticker, start_date, end_date)
        update_current_market_data(ticker)
        
        if df is not None and not df.empty:
            tot_ret, max_dd, trades, chart_html, df = run_macd_momentum(df, fast_ema, slow_ema, signal_line)
            
            # --- DATABASE SAVING LOGIC ---
            strategy_obj, created = Strategy.objects.get_or_create(
                name="MACD Momentum",
                defaults={'description': 'Moving Average Convergence Divergence momentum strategy.'}
            )
            
            sim_initial_balance = 10000.00
            sim_final_balance = sim_initial_balance * (1 + (tot_ret / 100))
            
            asset_obj, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
            
            Simulation.objects.filter(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date
            ).delete()
            
            simulation_obj = Simulation.objects.create(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date,
                initial_balance=sim_initial_balance,
                final_balance=sim_final_balance
            )
            
            _populate_simulation_data(simulation_obj, ticker, df)

            SavedBacktest.objects.filter(
                user=request.user,
                strategy_name="MACD Momentum",
                ticker=ticker.upper(),
                parameters=f"Fast: {fast_ema}, Slow: {slow_ema}, Signal: {signal_line}"
            ).delete()

            SavedBacktest.objects.create(
                user=request.user,
                strategy_name="MACD Momentum",
                ticker=ticker.upper(),
                parameters=f"Fast: {fast_ema}, Slow: {slow_ema}, Signal: {signal_line}",
                total_return=tot_ret,
                max_drawdown=max_dd,
                total_trades=trades
            )
            
            context.update({'backtest_run': True, 'total_return': tot_ret, 'max_drawdown': max_dd, 'total_trades': trades, 'chart_html': chart_html})
        else:
            context['error'] = "Could not fetch data."
            
    return render(request, 'trading/strategy3.html', context)


@login_required
def strategy4_view(request):
    """Strategy 4: Bollinger Bands Volatility"""
    context = {}
    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        sma_window = int(request.POST.get('sma_window'))
        std_dev = float(request.POST.get('std_dev'))
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        context.update({'ticker': ticker, 'sma_window': sma_window, 'std_dev': std_dev, 'start_date': start_date, 'end_date': end_date})
        
        df = get_historical_data_for_math(ticker, start_date, end_date)
        update_current_market_data(ticker)
        
        if df is not None and not df.empty:
            tot_ret, max_dd, trades, chart_html, df = run_bollinger_bands(df, sma_window, std_dev)
            
            # --- DATABASE SAVING LOGIC ---
            strategy_obj, created = Strategy.objects.get_or_create(
                name="Bollinger Bands",
                defaults={'description': 'Bollinger Bands mean reversion and breakout strategy.'}
            )
            
            sim_initial_balance = 10000.00
            sim_final_balance = sim_initial_balance * (1 + (tot_ret / 100))
            
            asset_obj, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
            
            Simulation.objects.filter(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date
            ).delete()
            
            simulation_obj = Simulation.objects.create(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date,
                initial_balance=sim_initial_balance,
                final_balance=sim_final_balance
            )
            
            _populate_simulation_data(simulation_obj, ticker, df)

            SavedBacktest.objects.filter(
                user=request.user,
                strategy_name="Bollinger Bands",
                ticker=ticker.upper(),
                parameters=f"SMA: {sma_window}, StdDev: {std_dev}"
            ).delete()

            SavedBacktest.objects.create(
                user=request.user,
                strategy_name="Bollinger Bands",
                ticker=ticker.upper(),
                parameters=f"SMA: {sma_window}, StdDev: {std_dev}",
                total_return=tot_ret,
                max_drawdown=max_dd,
                total_trades=trades
            )
            
            context.update({'backtest_run': True, 'total_return': tot_ret, 'max_drawdown': max_dd, 'total_trades': trades, 'chart_html': chart_html})
        else:
            context['error'] = "Could not fetch data."
            
    return render(request, 'trading/strategy4.html', context)


@login_required
def strategy5_view(request):
    """Strategy 5: VWAP Execution"""
    context = {}
    if request.method == 'POST':
        ticker = request.POST.get('ticker')
        timeframe = request.POST.get('timeframe')
        volume_threshold = request.POST.get('volume_threshold')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        context.update({'ticker': ticker, 'timeframe': timeframe, 'volume_threshold': volume_threshold, 'start_date': start_date, 'end_date': end_date})
        
        df = get_historical_data_for_math(ticker, start_date, end_date)
        update_current_market_data(ticker)
        
        if df is not None and not df.empty:
            tot_ret, max_dd, trades, chart_html, df = run_vwap_execution(df)
            
            # --- DATABASE SAVING LOGIC ---
            strategy_obj, created = Strategy.objects.get_or_create(
                name="VWAP Trend",
                defaults={'description': 'Volume Weighted Average Price execution strategy.'}
            )
            
            sim_initial_balance = 10000.00
            sim_final_balance = sim_initial_balance * (1 + (tot_ret / 100))
            
            asset_obj, _ = Asset.objects.get_or_create(ticker=ticker.upper(), defaults={'name': ticker.upper()})
            
            Simulation.objects.filter(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date
            ).delete()
            
            simulation_obj = Simulation.objects.create(
                user=request.user,
                strategy=strategy_obj,
                asset=asset_obj,
                start_date=start_date,
                end_date=end_date,
                initial_balance=sim_initial_balance,
                final_balance=sim_final_balance
            )
            
            _populate_simulation_data(simulation_obj, ticker, df)

            SavedBacktest.objects.filter(
                user=request.user,
                strategy_name="VWAP Trend",
                ticker=ticker.upper(),
                parameters=f"TF: {timeframe}, Vol Thresh: {volume_threshold}%"
            ).delete()

            SavedBacktest.objects.create(
                user=request.user,
                strategy_name="VWAP Trend",
                ticker=ticker.upper(),
                parameters=f"TF: {timeframe}, Vol Thresh: {volume_threshold}%",
                total_return=tot_ret,
                max_drawdown=max_dd,
                total_trades=trades
            )
            
            context.update({'backtest_run': True, 'total_return': tot_ret, 'max_drawdown': max_dd, 'total_trades': trades, 'chart_html': chart_html})
        else:
            context['error'] = "Could not fetch data."
            
    return render(request, 'trading/strategy5.html', context)


@login_required
def add_to_watchlist(request):
    """Saves or removes a stock from the user's Watchlist table"""
    if request.method == 'POST':
        ticker_input = request.POST.get('ticker')
        action = request.POST.get('action', 'add')
        
        if ticker_input:
            ticker_upper = ticker_input.upper()
            
            # 1. Get or Create the Asset first
            asset_obj, created = Asset.objects.get_or_create(
                ticker=ticker_upper, 
                defaults={'name': ticker_upper} 
            )
            
            if action == 'remove':
                Watchlist.objects.filter(user=request.user, asset=asset_obj).delete()
            else:
                # 2. Link the User and the Asset in the Watchlist table
                Watchlist.objects.get_or_create(
                    user=request.user, 
                    asset=asset_obj
                )
            
            # If they came from the asset detail page, redirect back there
            referer = request.META.get('HTTP_REFERER')
            if referer and f'/asset/{ticker_upper}' in referer:
                return redirect('asset_detail', ticker=ticker_upper)
                
    return redirect('dashboard')


@login_required
def asset_detail(request, ticker):
    """Shows the market data analytics chart and past backtests for a specific asset."""
    from django.shortcuts import get_object_or_404
    import plotly.graph_objects as go
    from plotly.io import to_html
    from .models import MarketData
    
    ticker = ticker.upper()
    asset = get_object_or_404(Asset, ticker=ticker)
    
    # Check if in watchlist
    in_watchlist = Watchlist.objects.filter(user=request.user, asset=asset).exists()
    
    # Get all saved backtests for this asset by this user
    saved_backtests = SavedBacktest.objects.filter(user=request.user, ticker=ticker).order_by('-created_at')
    
    # Get MarketData for chart
    market_data = MarketData.objects.filter(asset=asset).order_by('date')
    
    chart_html = ""
    if market_data.exists():
        dates = [md.date for md in market_data]
        prices = [float(md.close_price) for md in market_data]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, 
            y=prices, 
            name='Close Price', 
            line=dict(color='#38bdf8', width=2),
            fill='tozeroy',
            fillcolor='rgba(56, 189, 248, 0.1)'
        ))
        
        fig.update_layout(
            title=f"{asset.ticker} 1-Year Price History",
            paper_bgcolor='#1e293b',
            plot_bgcolor='#1e293b',
            font=dict(color='#cbd5e1'),
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor='#334155'),
            yaxis=dict(showgrid=True, gridcolor='#334155'),
            hovermode='x unified'
        )
        chart_html = to_html(fig, full_html=False)
        
    context = {
        'asset': asset,
        'in_watchlist': in_watchlist,
        'saved_backtests': saved_backtests,
        'chart_html': chart_html,
    }
    return render(request, 'trading/asset_detail.html', context)