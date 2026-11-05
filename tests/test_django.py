import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client
from core.models import Customer, Invoice, Payment, PaymentAllocation
from core.services import allocate


@pytest.mark.django_db
def test_auth_required():
    assert Client().get("/api/reports/summary/").status_code in (401, 403)


@pytest.mark.django_db
def test_dashboard_login():
    assert Client().get("/").status_code == 302


@pytest.mark.django_db
def test_allocation_prevents_double_spend():
    user = User.objects.create_user("tester", password="safe-password", is_staff=True)
    c = Customer.objects.create(name="A")
    inv = Invoice.objects.create(
        number="A-1",
        customer=c,
        issued_on=date.today(),
        due_on=date.today(),
        amount=Decimal("10"),
    )
    pay = Payment.objects.create(
        customer=c, reference="R", paid_on=date.today(), amount=Decimal("10")
    )
    allocate(invoice_id=inv.id, payment_id=pay.id, amount="10.00", user=user)
    with pytest.raises(ValidationError):
        allocate(invoice_id=inv.id, payment_id=pay.id, amount="1.00", user=user)
    assert PaymentAllocation.objects.count() == 1


@pytest.mark.django_db
def test_summary_reconciles():
    u = User.objects.create_user("reader", password="safe-password")
    client = Client()
    client.force_login(u)
    assert client.get("/api/reports/summary/").json()["outstanding"] == "0"
