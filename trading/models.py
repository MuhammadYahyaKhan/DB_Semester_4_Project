from django.db import models
from django.contrib.auth.models import User


# Trader  Profile
class TraderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_balance = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00)

    def __str__(self):
        return f"{self.user.username}'s Profile"


# TABLE 2: Asset (The Stocks)

class Asset(models.Model):
    ticker = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.ticker


# TABLE 3: Market Data (Purani kematein)

class MarketData(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField(default=0)

    def __str__(self):
        return f"{self.asset.ticker} on {self.date}"


# TABLE 4: Strategy (Satte ke tareeke)

class Strategy(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# TABLE 5: Simulation (The Backtest Run)

class Simulation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    strategy = models.ForeignKey(Strategy, on_delete=models.SET_NULL, null=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2)
    final_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Sim: {self.strategy.name} by {self.user.username}"


# TABLE 6: Simulated Trade (satta kaisi lage ga past mei stratgy ke hisab se)

class SimulatedTrade(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    trade_date = models.DateField()
    action = models.CharField(max_length=4) # 'BUY' or 'SELL'
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.action} {self.quantity} {self.asset.ticker}"


# TABLE 7: Equity Curve (Analytics ke liye use hoga)

class EquityCurve(models.Model):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    date = models.DateField()
    equity_value = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"${self.equity_value} on {self.date}"


# TABLE 8: Watchlist (User stock save kere ga)

class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    added_on = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.asset.ticker} watched by {self.user.username}"
    

class SavedBacktest(models.Model):
    # kis user ne chlaya hai ye backtest
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # wo user kya test ker rha hai
    strategy_name = models.CharField(max_length=100)  # e.g., "Moving Average Crossover"
    ticker = models.CharField(max_length=20)          # e.g., "AAPL"
    
    # 3. konsi stratgy use ker rha hai 
    parameters = models.CharField(max_length=255)     # e.g., "Short SMA: 50, Long SMA: 200"
    
    # 4. ka result aye
    total_return = models.FloatField()                # e.g., 25.5
    max_drawdown = models.FloatField()                # e.g., -12.4
    total_trades = models.IntegerField()              # e.g., 15
    
    # 5. date kya thi save kerne ki
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} | {self.ticker} | {self.strategy_name} | {self.total_return}%"