"""Explainable candidate matching. No automatic financial postings.

All amounts must be positive two-decimal strings; available balances may be zero.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation

ZERO = Decimal('0.00')


def money(value, *, allow_zero=False):
    if isinstance(value, bool):
        raise ValueError('Invalid amount')
    try:
        number = Decimal(str(value))
        if (not number.is_finite() or (number < 0 if allow_zero else number <= 0)
                or number.as_tuple().exponent < -2):
            raise ValueError('Amount must be nonnegative and have at most two decimals')
        return number.quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid amount') from exc


def suggest(invoices, payments, baseline=False):
    """Return reviewed suggestions, never allocations.

    Only unique same-customer references can suggest a target. Exact amount is
    a lower-confidence fallback requiring review. Already-used balances are
    excluded. A duplicate reference across the input batch is a review case.
    """
    references = Counter(
        (str(p['customer_id']), str(p.get('reference', '')).strip())
        for p in payments if str(p.get('reference', '')).strip()
    )
    output = []
    for payment in payments:
        pid = str(payment['id'])
        customer = str(payment['customer_id'])
        ref = str(payment.get('reference') or '').strip()
        hint = str(payment.get('invoice_hint') or '').strip()
        original = money(payment['amount'])
        available = money(payment.get('unallocated', original), allow_zero=True)
        if available > original:
            raise ValueError('Payment available exceeds amount')

        def record(invoice=None, reason='UNMATCHED', allocation=None):
            output.append({
                'payment_id': pid,
                'invoice_id': str(invoice['id']) if invoice is not None else None,
                'reason': reason, 'status': 'review',
                'amount': str(allocation if allocation is not None else available),
            })

        if available == ZERO:
            record(reason='ALREADY_ALLOCATED')
            continue
        if not baseline and ref and references[(customer, ref)] > 1:
            record(reason='DUPLICATE_REFERENCE')
            continue
        eligible = []
        for inv in invoices:
            if str(inv['customer_id']) != customer:
                continue
            total = money(inv['amount'])
            outstanding = money(inv.get('outstanding', total), allow_zero=True)
            if outstanding > total:
                raise ValueError('Invoice outstanding exceeds amount')
            if outstanding:
                eligible.append((inv, outstanding))
        if baseline:
            candidates = [(i, remaining) for i, remaining in eligible if ref and str(i['number']) == ref]
            reason = 'REFERENCE_MATCH'
        else:
            candidates = [(i, remaining) for i, remaining in eligible
                          if (hint and str(i['number']) == hint) or (ref and str(i['number']) == ref)]
            reason = 'REFERENCE_MATCH'
            if not candidates:
                candidates = [(i, remaining) for i, remaining in eligible if remaining == available]
                reason = 'AMOUNT_ONLY_REVIEW'
        if len(candidates) > 1:
            record(reason='AMBIGUOUS')
        elif not candidates:
            record(reason='UNMATCHED')
        else:
            invoice, remaining = candidates[0]
            if reason == 'AMOUNT_ONLY_REVIEW':
                code = reason
            elif available > remaining:
                code = 'OVERPAYMENT_REVIEW'
            elif available < remaining:
                code = 'PARTIAL_PAYMENT'
            else:
                code = 'REFERENCE_MATCH'
            record(invoice, code, min(available, remaining))
    return output
