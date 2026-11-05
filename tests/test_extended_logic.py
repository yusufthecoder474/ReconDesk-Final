"""Pure matching regression tests, independent of Django and Flask."""
import pytest
from core.logic import money, suggest


def inv(id, num, amount, customer=1, **kwargs):
    return {'id': id, 'number': num, 'amount': amount, 'customer_id': customer, **kwargs}


def pay(id, reference, amount, customer=1, hint='', **kwargs):
    return {'id': id, 'reference': reference, 'amount': amount,
            'customer_id': customer, 'invoice_hint': hint, **kwargs}


def test_consumed_payment_is_not_suggested():
    result = suggest([inv(1, 'I-1', '100.00')],
                     [pay(1, 'I-1', '100.00', unallocated='0.00')])
    assert result[0]['reason'] == 'ALREADY_ALLOCATED'
    assert result[0]['invoice_id'] is None


def test_paid_invoice_is_not_candidate():
    result = suggest([inv(1, 'I-1', '100.00', outstanding='0.00')],
                     [pay(1, 'I-1', '100.00')])
    assert result[0]['reason'] == 'UNMATCHED'


def test_partial_balance_limits_suggestion():
    result = suggest([inv(1, 'I-1', '100.00', outstanding='25.00')],
                     [pay(1, 'P-1', '100.00', hint='I-1', unallocated='60.00')])
    assert result[0]['reason'] == 'OVERPAYMENT_REVIEW'
    assert result[0]['amount'] == '25.00'


def test_ambiguous_amount_not_auto_assigned():
    result = suggest([inv(1, 'I-1', '50.00'), inv(2, 'I-2', '50.00')],
                     [pay(1, 'bank-1', '50.00')])
    assert result[0]['reason'] == 'AMBIGUOUS'
    assert result[0]['invoice_id'] is None


def test_duplicate_both_records_flagged():
    result = suggest([inv(1, 'I-1', '100.00')],
                     [pay(1, 'repeat', '100.00'), pay(2, 'repeat', '100.00')])
    assert [r['reason'] for r in result] == ['DUPLICATE_REFERENCE'] * 2


def test_duplicate_cross_customer_not_flagged():
    result = suggest([inv(1, 'I-1', '100.00'), inv(2, 'I-2', '50.00', customer=2)],
                     [pay(1, 'X', '100.00', hint='I-1'),
                      pay(2, 'X', '50.00', customer=2, hint='I-2')])
    assert all(r['invoice_id'] for r in result)


def test_baseline_reference_detected():
    result = suggest([inv(1, 'I-1', '100.00')], [pay(1, 'I-1', '100.00')], baseline=True)
    assert result[0]['invoice_id'] == '1'


def test_negative_available_fails():
    with pytest.raises(ValueError):
        suggest([inv(1, 'I-1', '100.00')], [pay(1, 'I-1', '100.00', unallocated='-5')])


def test_available_above_payment_amount_fails():
    with pytest.raises(ValueError):
        suggest([inv(1, 'I-1', '100.00')], [pay(1, 'I-1', '100.00', unallocated='101.00')])


def test_money_zero_only_when_opted_in():
    with pytest.raises(ValueError):
        money('0.00')
    assert str(money('0', allow_zero=True)) == '0.00'
