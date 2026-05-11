from django.contrib import admin
from django.urls import path, include  # <-- Make sure 'include' is imported here

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('trading.urls')),  # <-- This forwards traffic to your trading app
]