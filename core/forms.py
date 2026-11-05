from django import forms
from .models import Customer, Invoice, Payment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email"]


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["number", "customer", "issued_on", "due_on", "amount"]
        widgets = {
            "issued_on": forms.DateInput(attrs={"type": "date"}),
            "due_on": forms.DateInput(attrs={"type": "date"}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["customer", "reference", "invoice_hint", "paid_on", "amount"]
        widgets = {"paid_on": forms.DateInput(attrs={"type": "date"})}
