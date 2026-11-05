"""Real InnoDB concurrency check. Never treat SQLite as proof of locking."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from core.models import Customer, Invoice, Payment, PaymentAllocation
from core.services import allocate


@pytest.mark.mysql
@pytest.mark.django_db(transaction=True)
def test_same_invoice_concurrent_payment_cannot_overspend():
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.mysql':
        pytest.skip('Requires MySQL/InnoDB; SQLite select_for_update is not equivalent')
    staff = User.objects.create_user('worker', password='safe-demo-password', is_staff=True)
    customer = Customer.objects.create(name='Concurrent Demo')
    invoice = Invoice.objects.create(number='CONCURRENT-01', customer=customer,
                                     issued_on=date.today(), due_on=date.today(), amount=Decimal('10.00'))
    payments = [Payment.objects.create(customer=customer, reference=f'P-{n}',
                                       paid_on=date.today(), amount=Decimal('10.00')) for n in range(2)]

    def attempt(payment_id):
        close_old_connections()
        try:
            allocate(invoice_id=invoice.id, payment_id=payment_id, amount='10.00', user=staff)
            return 'posted'
        except ValidationError:
            return 'rejected'
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [p.pk for p in payments]))
    assert sorted(outcomes) == ['posted', 'rejected']
    assert PaymentAllocation.objects.filter(invoice=invoice).count() == 1
    assert sum(a.amount for a in invoice.allocations.all()) == Decimal('10.00')
