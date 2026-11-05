import pytest
from core.logic import money,suggest
I=[{'id':1,'number':'INV-1','customer_id':1,'amount':'5000.00'},{'id':2,'number':'INV-2','customer_id':1,'amount':'700.00'}]
def payment(ref='P-1',hint='INV-1',amount='5000.00',id=1,customer=1):return {'id':id,'reference':ref,'invoice_hint':hint,'amount':amount,'customer_id':customer}
def test_exact_match(): assert suggest(I,[payment(ref='INV-1')])[0]['reason']=='REFERENCE_MATCH'
def test_partial(): assert suggest(I,[payment(amount='3000.00')])[0]['reason']=='PARTIAL_PAYMENT'
def test_overpayment(): assert suggest(I,[payment(amount='6000.00')])[0]['reason']=='OVERPAYMENT_REVIEW'
def test_unmatched(): assert suggest(I,[payment(hint='',amount='123.00')])[0]['reason']=='UNMATCHED'
def test_amount_only_review(): assert suggest(I,[payment(hint='',amount='700.00')])[0]['reason']=='AMOUNT_ONLY_REVIEW'
def test_duplicate(): assert suggest(I,[payment(),payment(id=2)])[1]['reason']=='DUPLICATE_REFERENCE'
def test_baseline_no_hint(): assert suggest(I,[payment(ref='P-1')],baseline=True)[0]['reason']=='UNMATCHED'
def test_customer_mismatch(): assert suggest(I,[payment(customer=2)])[0]['reason']=='UNMATCHED'
@pytest.mark.parametrize('value',['-1','0','NaN','Infinity','1.234','hello',True])
def test_invalid_money(value):
    with pytest.raises(ValueError):money(value)
def test_decimal_money(): assert str(money('0.10'))=='0.10'
