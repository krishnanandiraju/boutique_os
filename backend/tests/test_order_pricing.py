from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import seed_data
from app.models import Merchant

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine);Base.metadata.create_all(bind=engine)
    with SessionLocal() as db: seed_data(db)
    with TestClient(app) as client: yield client


def order(client,tailoring=False):
    item=client.post('/api/items',json={'name':'Test fabric','inventory_type':'YARDAGE','category':'Fabric','selling_price':'1000','quantity':'10'}).json()
    result=client.post('/api/orders',json={'customer_id':1,'lines':[{'item_id':item['id'],'quantity':'2.5','requires_tailoring':tailoring}]})
    assert result.status_code==200,result.text
    return result.json()


def rule(client,**changes):
    result=client.post('/api/v2/discount-rules',json={'name':'Test discount','kind':'PERCENTAGE','scope':'ORDER','value':'10','requires_reason':True,**changes})
    assert result.status_code==200,result.text
    return result.json()


def apply(client,order,rule,**changes):
    return client.post(f"/api/v2/orders/{order['id']}/discounts",json={'rule_id':rule['id'],'reason':'Repeat customer',**changes})


def test_discount_updates_persisted_total_dashboard_and_audit(client):
    o=order(client);r=rule(client)
    before=Decimal(client.get('/api/dashboard').json()['sales_today'])
    response=apply(client,o,r);assert response.status_code==201,response.text
    pricing=response.json();assert pricing['subtotal']=='2500.00';assert pricing['discount_total']=='250.00';assert pricing['total']=='2250.00'
    assert client.get(f"/api/orders/{o['id']}").json()['total_amount']=='2250.00'
    assert Decimal(client.get('/api/dashboard').json()['sales_today'])==before-Decimal('250')
    events=client.get('/api/integrations/outbox?event_type=order.discount.applied').json()
    assert len(events)==1;assert events[0]['payload_json']['total']=='2250.00'
    assert apply(client,o,r).status_code==409


def test_reversal_is_audited_and_retry_is_idempotent(client):
    o=order(client);r=rule(client);pricing=apply(client,o,r).json();id=pricing['adjustments'][0]['id']
    path=f"/api/v2/orders/{o['id']}/discounts/{id}/reverse"
    response=client.post(path,json={'reason':'Entered wrong promotion'});assert response.status_code==200
    assert response.json()['total']=='2500.00';assert len(response.json()['adjustments'])==2
    assert response.json()['adjustments'][0]['active'] is False
    assert client.post(path,json={'reason':'Retry'}).json()['total']=='2500.00'
    assert apply(client,o,r).status_code==201


def test_line_then_order_stack_uses_remaining_balance(client):
    o=order(client);line=rule(client,scope='LINE',value='20',stackable=True);order_rule=rule(client,name='Second',stackable=True)
    a=apply(client,o,line,order_line_id=o['lines'][0]['id']);assert a.status_code==201
    b=apply(client,o,order_rule);assert b.status_code==201;assert b.json()['total']=='1800.00'
    earliest=b.json()['adjustments'][0]['id']
    assert client.post(f"/api/v2/orders/{o['id']}/discounts/{earliest}/reverse",json={'reason':'Undo'}).status_code==409


def test_cap_and_flat_discount_cannot_make_negative_total(client):
    o=order(client);r=rule(client,value='50',max_amount='100');assert apply(client,o,r).json()['total']=='2400.00'
    other=order(client);flat=rule(client,kind='FLAT',value='99999');assert apply(client,other,flat).json()['total']=='0.00'


def test_reason_approval_scope_and_tenant_are_enforced(client):
    o=order(client);r=rule(client)
    assert apply(client,o,r,reason=' ').status_code==422
    assert apply(client,o,r,order_line_id=o['lines'][0]['id']).status_code==422
    guarded=rule(client,approval_above_value='5');assert apply(client,o,guarded).status_code==409
    with SessionLocal() as db:
        merchant=Merchant(name='Other boutique');db.add(merchant);db.commit();merchant_id=merchant.id
    foreign=rule(client,merchant_id=merchant_id)
    assert apply(client,o,foreign).status_code==404
    assert client.get(f"/api/v2/orders/{o['id']}/pricing?merchant_id={merchant_id}").status_code==404
    line=rule(client,scope='LINE');assert apply(client,o,line,order_line_id=99999).status_code==422


def test_nonstackable_rule_and_wrong_order_line_are_rejected(client):
    o=order(client);first=rule(client);second=rule(client,name='Second',stackable=True)
    assert apply(client,o,first).status_code==201;assert apply(client,o,second).status_code==409
    other=order(client);line=rule(client,scope='LINE')
    assert apply(client,other,line,order_line_id=o['lines'][0]['id']).status_code==422


def test_fulfilment_requires_ready_and_locks_pricing(client):
    o=order(client);r=rule(client)
    path=f"/api/orders/{o['id']}/status"
    assert client.patch(path,json={'status':'DELIVERED'}).status_code==409
    assert client.patch(path,json={'status':'READY'}).status_code==200
    assert client.patch(path,json={'status':'PACKED'}).status_code==200
    assert apply(client,o,r).status_code==409
    assert client.patch(path,json={'status':'DELIVERED'}).status_code==200
    assert client.patch(path,json={'status':'CONFIRMED'}).status_code==409
    assert client.patch(path,json={'status':'DELIVERED'}).status_code==200


def test_pending_tailoring_cannot_be_marked_ready(client):
    o=order(client,tailoring=True)
    assert client.patch(f"/api/orders/{o['id']}/status",json={'status':'READY'}).status_code==409
