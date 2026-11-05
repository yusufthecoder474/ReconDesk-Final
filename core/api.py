from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum
from rest_framework import generics, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import AuditEvent, Invoice, Payment, PaymentAllocation
from .serializers import InvoiceSerializer, PaymentSerializer
from .services import allocate, start_reconciliation


class StaffWrite(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.method in permissions.SAFE_METHODS or request.user.is_staff
        ))


class Invoices(generics.ListCreateAPIView):
    queryset = Invoice.objects.all().order_by('-id')
    serializer_class = InvoiceSerializer
    permission_classes = [StaffWrite]

    def perform_create(self, serializer):
        obj = serializer.save()
        AuditEvent.objects.create(actor=self.request.user, action='INVOICE_CREATED', details={'id': obj.pk})


class Payments(generics.ListCreateAPIView):
    queryset = Payment.objects.all().order_by('-id')
    serializer_class = PaymentSerializer
    permission_classes = [StaffWrite]

    def perform_create(self, serializer):
        obj = serializer.save()
        AuditEvent.objects.create(actor=self.request.user, action='PAYMENT_CREATED', details={'id': obj.pk})


@api_view(['POST'])
def run_reconciliation(request):
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)
    try:
        run, suggestions = start_reconciliation(user=request.user)
        return Response({'run_id': run.pk, 'suggestions': suggestions}, status=201)
    except ValidationError as exc:
        return Response({'error': exc.messages}, status=503)


@api_view(['POST'])
def confirm_allocation(request):
    if not request.user.is_staff:
        return Response({'error': 'Staff only'}, status=403)
    try:
        posted = allocate(
            invoice_id=int(request.data['invoice_id']),
            payment_id=int(request.data['payment_id']),
            amount=request.data['amount'], user=request.user,
        )
        return Response({'allocation_id': posted.pk}, status=201)
    except (KeyError, ValueError, TypeError, ValidationError) as exc:
        return Response({'error': str(exc)}, status=400)


@api_view(['GET'])
def summary(request):
    invoice_total = Invoice.objects.aggregate(v=Sum('amount'))['v'] or Decimal('0')
    payment_total = Payment.objects.aggregate(v=Sum('amount'))['v'] or Decimal('0')
    allocated = PaymentAllocation.objects.aggregate(v=Sum('amount'))['v'] or Decimal('0')
    return Response({
        'invoiced': str(invoice_total), 'received': str(payment_total),
        'allocated': str(allocated), 'outstanding': str(invoice_total - allocated),
        'unallocated_payments': str(payment_total - allocated),
    })
