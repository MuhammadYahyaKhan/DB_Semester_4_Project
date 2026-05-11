from django.urls import path
from . import views

urlpatterns = [
    # Auth URLs
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard & Detail URL
    path('dashboard/', views.dashboard, name='dashboard'),
    path('simulation/<int:sim_id>/', views.simulation_detail, name='simulation_detail'),
    
    # Strategy URLs
    path('strategy/1/', views.strategy1_view, name='strategy1'),
    path('strategy/2/', views.strategy2_view, name='strategy2'),
    path('strategy/3/', views.strategy3_view, name='strategy3'),
    path('strategy/4/', views.strategy4_view, name='strategy4'),
    path('strategy/5/', views.strategy5_view, name='strategy5'),

    path('watchlist/add/', views.add_to_watchlist, name='add_to_watchlist'),
    path('asset/<str:ticker>/', views.asset_detail, name='asset_detail'),
]