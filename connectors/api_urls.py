from django.urls import path

from . import views

urlpatterns = [
    path("sync/", views.trigger_sync, name="connector-sync"),
    path("runs/", views.sync_runs, name="connector-runs"),
]
