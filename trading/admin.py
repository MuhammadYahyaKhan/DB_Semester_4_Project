from django.contrib import admin
from .models import (
    TraderProfile, 
    Asset, 
    MarketData, 
    Strategy, 
    Simulation, 
    SimulatedTrade, 
    EquityCurve, 
    Watchlist,
    SavedBacktest
)

# Registering the 9 tables so they appear in the Admin Dashboard
admin.site.register(TraderProfile)
admin.site.register(Asset)
admin.site.register(MarketData)
admin.site.register(Strategy)
admin.site.register(Simulation)
admin.site.register(SimulatedTrade)
admin.site.register(EquityCurve)
admin.site.register(Watchlist)
admin.site.register(SavedBacktest)