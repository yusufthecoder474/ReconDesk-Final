from django.urls import path
from . import api

urlpatterns = [
    path("invoices/", api.Invoices.as_view()),
    path("payments/", api.Payments.as_view()),
    path("reconciliation/run/", api.run_reconciliation),
    path("reconciliation/confirm/", api.confirm_allocation),
    path("reports/summary/", api.summary),
]
