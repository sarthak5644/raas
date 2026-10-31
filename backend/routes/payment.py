"""
Payment Routes - Stripe integration for subscriptions and credits
"""
import os
import json
import stripe
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

from database import db, User, Payment, AuditLog

payment_bp = Blueprint('payment', __name__)

PLANS = {
    'daily': {
        'name': 'Daily Plan',
        'price': 4900,  # paise (₹49) — offer price, regular ₹79
        'original_price': 7900,  # paise (₹79)
        'currency': 'inr',
        'credits': 15,
        'duration_days': 1,
        'features': ['10 file uploads', '15 download credits', 'All quick analysis types', 'Advanced Analytics Engine (Stage 1)', 'PDF & Excel reports']
    },
    'weekly': {
        'name': 'Weekly Plan',
        'price': 19900,  # paise (₹199) — offer price, regular ₹299
        'original_price': 29900,  # paise (₹299)
        'currency': 'inr',
        'credits': 60,
        'duration_days': 7,
        'features': ['40 file uploads', '60 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'PDF & Excel reports']
    },
    'monthly': {
        'name': 'Monthly Plan',
        'price': 39900,  # paise (₹399) — offer price, regular ₹599
        'original_price': 59900,  # paise (₹599)
        'currency': 'inr',
        'credits': 150,
        'duration_days': 30,
        'features': ['150 file uploads', '150 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'Priority processing', 'All report formats']
    },
    'yearly': {
        'name': 'Yearly Plan',
        'price': 159900,  # paise (₹1599) — offer price, regular ₹1799
        'original_price': 179900,  # paise (₹1799)
        'currency': 'inr',
        'credits': 2000,
        'duration_days': 365,
        'features': ['Unlimited file uploads', '2000 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'Priority processing & support', 'All report formats']
    },
    'credits_10': {
        'name': '10 Download Credits',
        'price': 29900,  # paise (₹299)
        'currency': 'inr',
        'credits': 10,
        'duration_days': 365,
        'features': ['10 download credits', 'Never expires for 1 year']
    }
}

# Commercial plan is not self-serve — surfaced on the pricing page as
# "Connect with our Team" (mailto), not purchasable via checkout/demo-activate.
COMMERCIAL_PLAN = {
    'name': 'Commercial Plan',
    'contact_email': 'sales@vpresearchcompany.com',
    'features': ['Unlimited uploads & downloads', 'API access', 'Dedicated account manager', 'Custom integrations', 'Team seats & SLA', 'Custom invoicing (GST)']
}


def get_stripe():
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
    return stripe


@payment_bp.route('/plans', methods=['GET'])
def get_plans():
    return jsonify({'plans': PLANS, 'commercial': COMMERCIAL_PLAN}), 200


@payment_bp.route('/create-checkout', methods=['POST'])
@jwt_required()
def create_checkout():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    plan_id = data.get('plan_id')
    if plan_id not in PLANS:
        return jsonify({'error': 'Invalid plan'}), 400
    
    plan = PLANS[plan_id]
    stripe_client = get_stripe()
    
    if not stripe_client.api_key:
        # Demo mode - simulate payment
        return jsonify({
            'demo_mode': True,
            'message': 'Stripe not configured. In demo mode, payment is simulated.',
            'plan_id': plan_id,
            'plan': plan
        }), 200
    
    try:
        # Create or get Stripe customer
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = stripe_client.customers.create(
                email=user.email,
                name=user.full_name or user.username,
                metadata={'user_id': str(user.id)}
            )
            customer_id = customer.id
            user.stripe_customer_id = customer_id
            db.session.commit()
        
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        
        session = stripe_client.checkout.sessions.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': plan.get('currency', 'inr'),
                    'product_data': {
                        'name': plan['name'],
                        'description': ', '.join(plan['features']),
                    },
                    'unit_amount': plan['price'],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&plan={plan_id}",
            cancel_url=f"{frontend_url}/pricing",
            metadata={
                'user_id': str(user.id),
                'plan_id': plan_id,
            }
        )
        
        return jsonify({'checkout_url': session.url, 'session_id': session.id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@payment_bp.route('/demo-activate', methods=['POST'])
@jwt_required()
def demo_activate():
    """Demo endpoint to activate a plan without real payment."""
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    plan_id = data.get('plan_id')
    if plan_id not in PLANS:
        return jsonify({'error': 'Invalid plan'}), 400
    
    plan = PLANS[plan_id]
    was_same_plan = (user.plan == plan_id)

    if 'credits' in plan_id:
        user.download_credits += plan['credits']
    else:
        # Renewing the same plan OR switching to a different one — either way,
        # always extend the expiry fresh from now and ADD credits on top of
        # whatever the user already has (never reset to zero / overwrite).
        user.plan = plan_id
        user.plan_expiry = datetime.utcnow() + timedelta(days=plan['duration_days'])
        user.download_credits += plan['credits']

    # Record payment
    payment = Payment(
        user_id=user.id,
        amount=plan['price'] / 100,
        currency=plan.get('currency', 'inr'),
        status='paid',
        plan=plan_id,
        credits_added=plan['credits']
    )
    db.session.add(payment)
    db.session.commit()

    if 'credits' in plan_id:
        action_msg = f'Demo: {plan["credits"]} credits added to your account!'
    elif was_same_plan:
        action_msg = f'Demo: {plan["name"]} renewed — {plan["credits"]} credits added!'
    else:
        action_msg = f'Demo: Switched to {plan["name"]} — {plan["credits"]} credits added!'

    return jsonify({
        'message': action_msg,
        'user': user.to_dict()
    }), 200


@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    stripe_client = get_stripe()
    
    if webhook_secret:
        try:
            event = stripe_client.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    else:
        try:
            event = json.loads(payload)
        except:
            return jsonify({'error': 'Invalid payload'}), 400
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session.get('metadata', {}).get('user_id', 0))
        plan_id = session.get('metadata', {}).get('plan_id', '')
        
        user = User.query.get(user_id)
        if user and plan_id in PLANS:
            plan = PLANS[plan_id]
            
            if 'credits' in plan_id:
                user.download_credits += plan['credits']
            else:
                user.plan = plan_id
                user.plan_expiry = datetime.utcnow() + timedelta(days=plan['duration_days'])
                user.download_credits += plan['credits']
            
            payment = Payment(
                user_id=user.id,
                stripe_session_id=session.get('id'),
                stripe_payment_intent=session.get('payment_intent'),
                amount=session.get('amount_total', 0) / 100,
                currency=session.get('currency', 'inr'),
                status='paid',
                plan=plan_id,
                credits_added=plan['credits']
            )
            db.session.add(payment)
            db.session.commit()
    
    return jsonify({'status': 'ok'}), 200


@payment_bp.route('/history', methods=['GET'])
@jwt_required()
def payment_history():
    identity = get_jwt_identity()
    payments = Payment.query.filter_by(user_id=int(identity))\
        .order_by(Payment.created_at.desc()).all()
    
    return jsonify({'payments': [p.to_dict() for p in payments]}), 200