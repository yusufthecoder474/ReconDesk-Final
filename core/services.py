"""Posting financial allocations is allowed only via this service."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from .logic import money
from .models import AuditEvent, Invoice, Payment, PaymentAllocation, ReconciliationSuggestion


@transaction.atomic
def allocate(*, invoice_id, payment_id, amount, user):
    # Always lock invoice before payment to avoid reversed lock order.
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    try:
        value = money(amount)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if not user or not user.is_authenticated or not user.is_staff:
        raise ValidationError('Only staff may post allocations')
    if invoice.customer_id != payment.customer_id:
        raise ValidationError('Invoice and payment customers differ')
    invoice_used = sum((a.amount for a in PaymentAllocation.objects.filter(invoice=invoice)), Decimal('0.00'))
    payment_used = sum((a.amount for a in PaymentAllocation.objects.filter(payment=payment)), Decimal('0.00'))
    if value > invoice.amount - invoice_used:
        raise ValidationError('Invoice would be overallocated')
    if value > payment.amount - payment_used:
        raise ValidationError('Payment would be overallocated')
    if PaymentAllocation.objects.filter(invoice=invoice, payment=payment).exists():
        raise ValidationError('Allocation for this pair already exists')
    posted = PaymentAllocation.objects.create(invoice=invoice, payment=payment, amount=value)
    if not invoice.finalized:
        invoice.finalized = True
        invoice.save(update_fields=['finalized'])
    AuditEvent.objects.create(actor=user, action='PAYMENT_ALLOCATED', details={
        'invoice_id': invoice.pk, 'payment_id': payment.pk,
        'allocation_id': posted.pk, 'amount': str(value),
    })
    return posted


@transaction.atomic
def decide_suggestion(*, suggestion_id, approve, user):
    if not user or not user.is_authenticated or not user.is_staff:
        raise ValidationError('Staff only')
    suggestion = ReconciliationSuggestion.objects.select_for_update().get(pk=suggestion_id)
    if suggestion.status != 'review':
        raise ValidationError('Suggestion already processed')
    if not approve:
        suggestion.status = 'rejected'
        suggestion.save(update_fields=['status'])
        AuditEvent.objects.create(actor=user, action='SUGGESTION_REJECTED', details={'suggestion_id': suggestion.pk})
        return None
    if suggestion.invoice_id is None or suggestion.reason not in {
        'REFERENCE_MATCH', 'PARTIAL_PAYMENT', 'OVERPAYMENT_REVIEW', 'AMOUNT_ONLY_REVIEW'
    }:
        raise ValidationError('Suggestion requires manual investigation; no safe allocation target')
    posted = allocate(invoice_id=suggestion.invoice_id, payment_id=suggestion.payment_id,
                      amount=suggestion.suggested_amount, user=user)
    suggestion.status = 'confirmed'
    suggestion.save(update_fields=['status'])
    return posted


def start_reconciliation(*, user):
    """Query the Flask service and persist only reviewable suggestions."""
    import os
    import requests
    from .models import Payment, ReconciliationRun

    if not user or not user.is_authenticated or not user.is_staff:
        raise ValidationError('Staff only')
    invoices = [{
        'id': i.pk, 'number': i.number, 'customer_id': i.customer_id,
        'amount': str(i.amount), 'outstanding': str(i.outstanding),
    } for i in Invoice.objects.prefetch_related('allocations')]
    payments = [{
        'id': p.pk, 'customer_id': p.customer_id, 'reference': p.reference,
        'invoice_hint': p.invoice_hint, 'amount': str(p.amount),
        'unallocated': str(p.unallocated),
    } for p in Payment.objects.prefetch_related('allocations')]
    url = os.environ.get('MATCHER_URL', 'http://127.0.0.1:5000').rstrip('/') + '/api/match'
    try:
        response = requests.post(
            url, json={'invoices': invoices, 'payments': payments},
            headers={'X-Internal-Token': os.environ.get('MATCHER_SHARED_TOKEN', 'dev-token')},
            timeout=8,
        )
        response.raise_for_status()
        suggestions = response.json()['suggestions']
        if not isinstance(suggestions, list):
            raise ValueError('Invalid suggestions list')
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise ValidationError('Flask matcher is unavailable or returned invalid data') from exc

    payment_ids = {str(p['id']) for p in payments}
    invoice_ids = {str(i['id']) for i in invoices}
    for item in suggestions:
        try:
            payment_id = str(item['payment_id'])
            invoice_id = item['invoice_id']
            amount = money(item['amount'], allow_zero=True)
            if payment_id not in payment_ids or (invoice_id is not None and str(invoice_id) not in invoice_ids):
                raise ValueError('Unexpected reconciliation identifiers')
        except (TypeError, KeyError, ValueError) as exc:
            raise ValidationError('Malformed matching response') from exc
    with transaction.atomic():
        run = ReconciliationRun.objects.create(created_by=user)
        for item in suggestions:
            ReconciliationSuggestion.objects.create(
                run=run, payment_id=int(item['payment_id']),
                invoice_id=int(item['invoice_id']) if item['invoice_id'] is not None else None,
                reason=str(item['reason'])[:80],
                status='review',
                suggested_amount=money(item['amount'], allow_zero=True),
            )
        AuditEvent.objects.create(actor=user, action='RECONCILIATION_RUN', details={
            'run_id': run.pk, 'suggestion_count': len(suggestions),
        })
    return run, suggestions
