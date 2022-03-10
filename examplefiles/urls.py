import os

from django.contrib import admin
from django.urls import path, include

if os.getenv('MIGRATE', 'False') == 'True':
    urlpatterns = []
else:
    urlpatterns = [
        path('admin/', admin.site.urls),
        path('', include('call_for_volunteers.urls')),
    ]
