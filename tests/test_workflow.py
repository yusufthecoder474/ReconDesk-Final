"""End-to-end-ish Django tests for staff UI and financial posting.

These require Django, pytest-django and SQLite/MySQL. Not run in generation sandbox.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client
from core.models import AuditEvent, Customer, Invoice, Payment, PaymentAllocation, ReconciliationSuggestion
from core.services import allocate, decide_suggestion


@pytest.fixture
def finance(db):
    staff = User.objects.create_user('accountant', password='safe-demo-password', is_staff=True)
    customer = Customer.objects.create(name='Local Shop')
    invoice = Invoice.objects.create(number='IN-100', customer=customer, issued_on=date.today(),
                                     due_on=date.today(), amount=Decimal('5000.00'))
    payment = Payment.objects.create(customer=customer, reference='BANK-101',
                                     invoice_hint='IN-100', paid_on=date.today(), amount=Decimal('3000.00'))
    return staff, customer, invoice, payment


def test_customers_require_staff(finance):
    staff, *_ = finance
    viewer = User.objects.create_user('viewer', password='safe-demo-password')
    browser = Client()
    browser.force_login(viewer)
    response = browser.post('/customers/', {'name': 'Other'}, follow=False)
    assert response.status_code == 403
    assert Customer.objects.count() == 1
    browser.force_login(staff)
    response = browser.post('/customers/', {'name': 'Other'}, follow=False)
    assert response.status_code == 302
    assert Customer.objects.count() == 2


def test_partial_payment_finalizes_invoice(finance):
    staff, _, invoice, payment = finance
    allocate(invoice_id=invoice.pk, payment_id=payment.pk, amount='3000.00', user=staff)
    invoice.refresh_from_db()
    assert invoice.finalized is True
    assert invoice.outstanding == Decimal('2000.00')
    assert payment.unallocated == Decimal('0.00')
    with pytest.raises(ValidationError):
        invoice.amount = Decimal('9000.00')
        invoice.save()


def test_reconciliation_ui_with_mocked_flask(finance):
    staff, _, invoice, payment = finance
    browser = Client()
    browser.force_login(staff)
    payload = {'suggestions': [
        {'payment_id': str(payment.pk), 'invoice_id': str(invoice.pk),
         'amount': '3000.00', 'reason': 'PARTIAL_PAYMENT', 'status': 'review'}]}
    reply = Mock()
    reply.json.return_value = payload
    reply.raise_for_status.return_value = None
    with patch('requests.post', return_value=reply) as request_post:
        result = browser.post('/reconcile/', {'action': 'run'})
    assert result.status_code == 302
    assert request_post.called
    suggestion = ReconciliationSuggestion.objects.get()
    result = browser.post('/reconcile/', {'action': 'approve', 'suggestion_id': suggestion.pk})
    assert result.status_code == 302
    suggestion.refresh_from_db()
    assert suggestion.status == 'confirmed'
    assert PaymentAllocation.objects.get().amount == Decimal('3000.00')
    assert AuditEvent.objects.filter(action='PAYMENT_ALLOCATED').exists()


def test_unsafe_duplicate_post_rejected(finance):
    staff, _, invoice, payment = finance
    allocate(invoice_id=invoice.pk, payment_id=payment.pk, amount='1000.00', user=staff)
    with pytest.raises(ValidationError):
        allocate(invoice_id=invoice.pk, payment_id=payment.pk, amount='1000.00', user=staff)


def test_invoice_filter(finance):
    staff, *_ = finance
    browser = Client()
    browser.force_login(staff)
    response = browser.get('/invoices/?status=unpaid')
    assert response.status_code == 200
    assert b'IN-100' in response.content


def test_match_service_failure_is_reported(finance):
    staff, *_ = finance
    browser = Client()
    browser.force_login(staff)
    with patch('requests.post', side_effect=__import__('requests').ConnectionError('offline')):
        result = browser.post('/reconcile/', {'action': 'run'}, follow=True)
    assert result.status_code == 200
    assert not ReconciliationSuggestion.objects.exists()


def test_delete_allocated_invoice_refused(finance):
    staff, _, invoice, payment = finance
    allocate(invoice_id=invoice.pk, payment_id=payment.pk, amount='1000.00', user=staff)
    browser = Client()
    browser.force_login(staff)
    response = browser.post(f'/invoices/{invoice.pk}/delete/')
    assert response.status_code == 302
    assert Invoice.objects.filter(pk=invoice.pk).exists()


def test_unallocated_invoice_delete_logs_audit(finance):
    staff, _, invoice, _ = finance
    browser = Client()
    browser.force_login(staff)
    response = browser.post(f'/invoices/{invoice.pk}/delete/')
    assert response.status_code == 302
    assert not Invoice.objects.filter(pk=invoice.pk).exists()
    assert AuditEvent.objects.filter(action='DRAFT_INVOICE_DELETED').exists()


def test_customer_delete_protects_financial_records(finance):
    staff, customer, _, _ = finance
    browser = Client()
    browser.force_login(staff)
    response = browser.post(f'/customers/{customer.pk}/delete/')
    assert response.status_code == 302
    assert Customer.objects.filter(pk=customer.pk).exists()
