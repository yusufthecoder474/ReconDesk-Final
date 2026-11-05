import csv
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CustomerForm, InvoiceForm, PaymentForm
from .models import AuditEvent, Customer, Invoice, Payment, PaymentAllocation, ReconciliationSuggestion
from .services import decide_suggestion, start_reconciliation


def staff(user):
    return user.is_authenticated and user.is_staff


@login_required
def dashboard(request):
    total = Invoice.objects.aggregate(x=Sum('amount'))['x'] or Decimal('0.00')
    received = Payment.objects.aggregate(x=Sum('amount'))['x'] or Decimal('0.00')
    reconciled = PaymentAllocation.objects.aggregate(x=Sum('amount'))['x'] or Decimal('0.00')
    invoices = list(Invoice.objects.prefetch_related('allocations'))
    payments = list(Payment.objects.prefetch_related('allocations'))
    return render(request, 'core/dashboard.html', {
        'total': total, 'received': received, 'reconciled': reconciled,
        'outstanding': total - reconciled,
        'partial': sum(1 for i in invoices if Decimal('0') < i.allocated < i.amount),
        'unmatched': sum(1 for p in payments if p.unallocated > 0),
        'exceptions': sum(1 for p in payments if p.unallocated > 0 and not p.invoice_hint),
    })


@login_required
def customers_page(request):
    form = CustomerForm(request.POST or None)
    if request.method == 'POST':
        if not staff(request.user):
            return HttpResponse('Staff only', status=403)
        if form.is_valid():
            customer = form.save()
            AuditEvent.objects.create(actor=request.user, action='CUSTOMER_CREATED', details={'id': customer.id})
            messages.success(request, 'Customer created')
            return redirect('customers')
    items = Customer.objects.filter(name__icontains=request.GET.get('q', '')).order_by('name')[:100]
    return render(request, 'core/list.html', {'heading': 'Customers', 'form': form, 'items': items, 'kind': 'customer'})


@user_passes_test(staff)
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user, action='CUSTOMER_UPDATED', details={'id': customer.pk})
        messages.success(request, 'Customer updated')
        return redirect('customers')
    return render(request, 'core/edit.html', {'form': form, 'heading': f'Edit customer {customer.name}'})


@user_passes_test(staff)
def delete_customer(request, customer_id):
    if request.method != 'POST':
        return HttpResponse('POST required', status=405)
    customer = get_object_or_404(Customer, pk=customer_id)
    if customer.invoice_set.exists() or customer.payment_set.exists():
        messages.error(request, 'Cannot delete a customer with financial records')
    else:
        name = customer.name
        customer.delete()
        AuditEvent.objects.create(actor=request.user, action='CUSTOMER_DELETED', details={'id': customer_id, 'name': name})
        messages.success(request, 'Customer deleted')
    return redirect('customers')


@login_required
def invoices_page(request):
    form = InvoiceForm(request.POST or None)
    if request.method == 'POST':
        if not staff(request.user):
            return HttpResponse('Staff only', status=403)
        if form.is_valid():
            invoice = form.save()
            AuditEvent.objects.create(actor=request.user, action='INVOICE_CREATED', details={'id': invoice.id})
            messages.success(request, 'Invoice created')
            return redirect('invoices')
    items = Invoice.objects.select_related('customer').prefetch_related('allocations').filter(
        Q(number__icontains=request.GET.get('q', '')) | Q(customer__name__icontains=request.GET.get('q', ''))
    ).order_by('-id')[:100]
    status_filter = request.GET.get('status', '')
    if status_filter in ('paid', 'partial', 'unpaid'):
        items = [i for i in items if (
            (status_filter == 'paid' and i.outstanding == 0) or
            (status_filter == 'partial' and 0 < i.allocated < i.amount) or
            (status_filter == 'unpaid' and i.allocated == 0)
        )]
    return render(request, 'core/list.html', {
        'heading': 'Invoices', 'form': form, 'items': items, 'kind': 'invoice',
        'status_filter': status_filter,
    })


@user_passes_test(staff)
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if invoice.finalized or invoice.allocations.exists():
        messages.error(request, 'Finalized or allocated invoices cannot be edited')
        return redirect('invoices')
    form = InvoiceForm(request.POST or None, instance=invoice)
    if request.method == 'POST' and form.is_valid():
        form.save()
        AuditEvent.objects.create(actor=request.user, action='INVOICE_UPDATED', details={'id': invoice.pk})
        messages.success(request, 'Invoice updated')
        return redirect('invoices')
    return render(request, 'core/edit.html', {'form': form, 'invoice': invoice})


@user_passes_test(staff)
def delete_invoice(request, invoice_id):
    if request.method != 'POST':
        return HttpResponse('POST required', status=405)
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if invoice.finalized or invoice.allocations.exists() or invoice.reconciliationsuggestion_set.exists():
        messages.error(request, 'Invoices with allocations, suggestions or finalization cannot be deleted')
    else:
        snapshot = {'id': invoice.pk, 'number': invoice.number, 'amount': str(invoice.amount)}
        invoice.delete()
        AuditEvent.objects.create(actor=request.user, action='DRAFT_INVOICE_DELETED', details=snapshot)
        messages.success(request, 'Draft invoice deleted')
    return redirect('invoices')


@login_required
def payments_page(request):
    form = PaymentForm(request.POST or None)
    if request.method == 'POST':
        if not staff(request.user):
            return HttpResponse('Staff only', status=403)
        if form.is_valid():
            payment = form.save()
            AuditEvent.objects.create(actor=request.user, action='PAYMENT_CREATED', details={'id': payment.id})
            messages.success(request, 'Payment recorded; duplicate references need review')
            return redirect('payments')
    items = Payment.objects.select_related('customer').prefetch_related('allocations').filter(
        Q(reference__icontains=request.GET.get('q', '')) |
        Q(customer__name__icontains=request.GET.get('q', ''))
    ).order_by('-id')[:100]
    return render(request, 'core/list.html', {'heading': 'Payments', 'form': form, 'items': items, 'kind': 'payment'})


@login_required
def reconcile_page(request):
    if request.method == 'POST':
        if not staff(request.user):
            return HttpResponse('Staff only', status=403)
        action = request.POST.get('action', '')
        try:
            if action == 'run':
                run, items = start_reconciliation(user=request.user)
                messages.success(request, f'Run {run.pk} created {len(items)} review suggestions')
            elif action in ('approve', 'reject'):
                suggestion_id = int(request.POST.get('suggestion_id', ''))
                decide_suggestion(suggestion_id=suggestion_id,
                                  approve=action == 'approve', user=request.user)
                messages.success(request, f'Suggestion {action}d')
            else:
                messages.error(request, 'Unknown action')
        except (ValidationError, ValueError, TypeError, ReconciliationSuggestion.DoesNotExist) as exc:
            messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        return redirect('reconcile')
    suggestions = ReconciliationSuggestion.objects.select_related('invoice', 'payment', 'run').order_by('-id')[:100]
    return render(request, 'core/reconcile.html', {'suggestions': suggestions})


@login_required
def export_report(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reconciliation.csv"'
    writer = csv.writer(response)
    writer.writerow(['invoice', 'customer', 'amount', 'allocated', 'outstanding'])
    for inv in Invoice.objects.select_related('customer').prefetch_related('allocations'):
        writer.writerow([inv.number, inv.customer.name, str(inv.amount), str(inv.allocated), str(inv.outstanding)])
    return response
