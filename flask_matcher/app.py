import os
from flask import Flask,jsonify,request
from core.logic import suggest,money
app=Flask(__name__)
@app.get('/health')
def health(): return jsonify(status='ok')
@app.post('/api/match')
def match():
    token=os.environ.get('MATCHER_SHARED_TOKEN','dev-token')
    if request.headers.get('X-Internal-Token')!=token: return jsonify(error='Unauthorized'),401
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or not isinstance(body.get('invoices'),list) or not isinstance(body.get('payments'),list): return jsonify(error='Expected invoices and payments arrays'),400
    if len(body['invoices'])>10000 or len(body['payments'])>10000: return jsonify(error='Request too large'),413
    try:
        for x in body['invoices']+body['payments']:
            if not isinstance(x,dict): raise ValueError('Record must be an object')
            for field in ('id','customer_id','amount'):
                if field not in x: raise ValueError('Missing '+field)
            money(x['amount'])
        return jsonify(suggestions=suggest(body['invoices'],body['payments'],baseline=bool(body.get('baseline',False))))
    except (ValueError,KeyError,TypeError) as exc: return jsonify(error=str(exc)),400
if __name__=='__main__': app.run(host='127.0.0.1',port=5000)
