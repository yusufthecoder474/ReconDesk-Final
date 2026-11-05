from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def positive_amount(value):
    if value is None or value <= 0:
        raise ValidationError("Amount must be positive")


class Customer(models.Model):
    name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    issued_on = models.DateField()
    due_on = models.DateField()
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[positive_amount]
    )
    finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.due_on and self.issued_on and self.due_on < self.issued_on:
            raise ValidationError("Due date precedes issue date")

    def save(self, *args, **kwargs):
        if self.pk:
            old = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "number",
                    "customer_id",
                    "issued_on",
                    "due_on",
                    "amount",
                    "finalized",
                )
                .first()
            )
            if (
                old
                and old["finalized"]
                and any(
                    old[f] != getattr(self, f)
                    for f in ("number", "customer_id", "issued_on", "due_on", "amount")
                )
            ):
                raise ValidationError("Finalized invoice cannot be modified")
            if old and old["finalized"] and not self.finalized:
                raise ValidationError("Finalized invoice cannot be reopened")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.number

    @property
    def allocated(self):
        return sum((a.amount for a in self.allocations.all()), Decimal("0.00"))

    @property
    def outstanding(self):
        return self.amount - self.allocated


class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    reference = models.CharField(max_length=80, db_index=True)
    invoice_hint = models.CharField(max_length=50, blank=True)
    paid_on = models.DateField()
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[positive_amount]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and PaymentAllocation.objects.filter(payment_id=self.pk).exists():
            old = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("customer_id", "reference", "invoice_hint", "paid_on", "amount")
                .first()
            )
            if old and any(
                old[f] != getattr(self, f)
                for f in (
                    "customer_id",
                    "reference",
                    "invoice_hint",
                    "paid_on",
                    "amount",
                )
            ):
                raise ValidationError("Allocated payment cannot be modified")
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def unallocated(self):
        return self.amount - sum(
            (a.amount for a in self.allocations.all()), Decimal("0.00")
        )


class PaymentAllocation(models.Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="allocations"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="allocations"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[positive_amount]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "payment"], name="unique_invoice_payment_allocation"
            )
        ]


class ReconciliationRun(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="complete")


class ReconciliationSuggestion(models.Model):
    run = models.ForeignKey(
        ReconciliationRun, on_delete=models.CASCADE, related_name="suggestions"
    )
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, null=True, blank=True
    )
    reason = models.CharField(max_length=80)
    status = models.CharField(max_length=30, default="review")
    suggested_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=80)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
