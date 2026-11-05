"""Financial postings and audit history are read-only in admin.

Use application services for allocations; never create them directly in admin.
"""
from django.contrib import admin
from .models import (AuditEvent, Customer, Invoice, Payment, PaymentAllocation,
                     ReconciliationRun, ReconciliationSuggestion)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email')
    search_fields = ('name',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'amount', 'finalized')
    search_fields = ('number',)
    readonly_fields = ('finalized',)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer', 'amount', 'paid_on')
    search_fields = ('reference',)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (PaymentAllocation, ReconciliationRun, ReconciliationSuggestion, AuditEvent):
    admin.site.register(model, ReadOnlyAdmin)
