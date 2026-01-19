import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
from transformers import pipeline
import os
from flask import Flask, request, jsonify
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

app = Flask(__name__)

limiter = Limiter(key_func=get_remote_address, app=app)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.register_blueprint(SlowAPIMiddleware().blueprint)

# CORS headers
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = '*'
    return response

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()

# AI Models setup
spam_classifier = pipeline("text-classification", model="martin-ha/toxic-comment-model")
abusive_classifier = pipeline("text-classification", model="unitary/toxic-bert")
suspicious_classifier = pipeline("text-classification", model="martin-ha/toxic-comment-model")  # Placeholder

def detect_spam(content: str) -> float:
    result = spam_classifier(content)
    return result[0]['score'] if result[0]['label'] == 'LABEL_1' else 1 - result[0]['score']

def detect_abusive(content: str) -> float:
    result = abusive_classifier(content)
    return result[0]['score'] if result[0]['label'] == 'toxic' else 0.0

def detect_suspicious(content: str) -> float:
    # Simple heuristic: suspicious if contains certain words
    suspicious_words = ['hack', 'scam', 'phish', 'malware']
    return 0.8 if any(word in content.lower() for word in suspicious_words) else 0.1

@app.route('/moderate', methods=['POST'])
def moderate_content():
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400

    content = data['content']
    user_id = data.get('user_id')

    logger.info(f"Moderating content from user {user_id}: {content[:50]}...")

    # AI detections
    spam_score = detect_spam(content)
    abusive_score = detect_abusive(content)
    suspicious_score = detect_suspicious(content)

    # Thresholds
    is_spam = spam_score > 0.7
    is_abusive = abusive_score > 0.7
    is_suspicious = suspicious_score > 0.7

    # Logic for auto-hide and send for review
    auto_hide = is_abusive or (is_spam and is_suspicious)
    send_for_review = is_suspicious or (spam_score > 0.5 and abusive_score > 0.5)

    # Flag in database
    if send_for_review:
        # Store in Firestore
        doc_ref = db.collection('moderation_queue').document()
        doc_ref.set({
            'content': content,
            'user_id': user_id,
            'spam_score': spam_score,
            'abusive_score': abusive_score,
            'suspicious_score': suspicious_score,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

    return jsonify({
        'is_spam': is_spam,
        'is_abusive': is_abusive,
        'is_suspicious': is_suspicious,
        'auto_hide': auto_hide,
        'send_for_review': send_for_review,
        'confidence_scores': {
            'spam': spam_score,
            'abusive': abusive_score,
            'suspicious': suspicious_score
        }
    })

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

# Firebase Functions entry point
from firebase_functions import https_fn

@https_fn.on_request()
def api(req):
    with app.request_context(req):
        return app.full_dispatch_request()
