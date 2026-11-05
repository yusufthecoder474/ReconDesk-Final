from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from django.urls import include, path
from core import views

urlpatterns = [
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health'),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('customers/', views.customers_page, name='customers'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('invoices/', views.invoices_page, name='invoices'),
    path('invoices/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),
    path('invoices/<int:invoice_id>/delete/', views.delete_invoice, name='delete_invoice'),
    path('payments/', views.payments_page, name='payments'),
    path('reconcile/', views.reconcile_page, name='reconcile'),
    path('reports/export/', views.export_report, name='export'),
    path('api/', include('core.api_urls')),
]
