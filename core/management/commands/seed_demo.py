from datetime import date,timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from core.models import Customer,Invoice,Payment
class Command(BaseCommand):
    help='Load deterministic synthetic sample data'
    def handle(self,*args,**kwargs):
        c,_=Customer.objects.get_or_create(name='Demo Customer',defaults={'email':'demo@example.invalid'})
        today=date(2026,11,5)
        for n,amt in [('INV-001','5000.00'),('INV-002','3500.00'),('INV-003','800.00')]:
            Invoice.objects.get_or_create(number=n,defaults={'customer':c,'issued_on':today,'due_on':today+timedelta(days=30),'amount':Decimal(amt)})
        for ref,hint,amt in [('PAY-001','INV-001','3000.00'),('PAY-002','INV-001','2000.00'),('PAY-003','INV-002','3000.00'),('PAY-004','','100.00')]:
            Payment.objects.get_or_create(reference=ref,customer=c,defaults={'invoice_hint':hint,'paid_on':today,'amount':Decimal(amt)})
        self.stdout.write(self.style.SUCCESS('Synthetic demo records ready'))
