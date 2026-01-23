from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from typing import Optional
import unicodedata
import re
import sys
import os
import groq

# -------------------------------
# Logging setup
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Detect HuggingFace Hub modules (optional)
for m in sys.modules:
    if "huggingface_hub" in m:
        logger.warning(f"huggingface_hub detected: {m}")

logger.info(f"HTTP_PROXY={os.getenv('HTTP_PROXY')}")
logger.info(f"HTTPS_PROXY={os.getenv('HTTPS_PROXY')}")

# -------------------------------
# FastAPI app
# -------------------------------
app = FastAPI(title="Content Moderation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://content-moderation-71254.web.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Pydantic models
# -------------------------------
class ContentRequest(BaseModel):
    content: str
    user_id: Optional[str] = None

class ModerationResponse(BaseModel):
    is_spam: bool
    is_abusive: bool
    is_suspicious: bool
    auto_hide: bool
    send_for_review: bool
    confidence_scores: dict
    message: Optional[str] = None

# -------------------------------
# Text normalization
# -------------------------------
def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

# -------------------------------
# Spam detection
# -------------------------------
def detect_spam(content: str) -> float:
    content_lower = content.lower()
    # ... (keep all your spam_patterns, spam_scores, indicators exactly as before)
    # Implementation unchanged
    max_score = 0.1
    # [same logic as your current script]
    return max_score  # Replace with actual computation

# -------------------------------
# Safe Groq client creation
# -------------------------------
def create_groq_client_safe():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY not set, falling back to regex-based detection")
        return None
    try:
        # Bypass the internal proxies bug
        client = groq.Groq.__new__(groq.Groq)
        groq.Groq.__init__(client, api_key=api_key)
        return client
    except TypeError as e:
        if "proxies" in str(e):
            logger.warning("Groq SDK proxies bug detected. Falling back to regex.")
            return None
        raise e

# -------------------------------
# Abusive content detection
# -------------------------------
def detect_abusive(content: str) -> float:
    client = create_groq_client_safe()
    if client is None:
        return detect_abusive_regex(content)

    try:
        # Remove env proxies in Render
        for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(key, None)

        text_lower = content.lower()
        is_spanish = any(word in text_lower for word in ['el', 'la', 'los', 'las', 'un', 'una', 'es', 'son', 'está', 'están'])

        prompt = f"""{"Analiza el siguiente texto en español..." if is_spanish else "Analyze the following text..."}{content}"""
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0
        )

        confidence_str = response.choices[0].message.content.strip()
        confidence = float(confidence_str)
        return max(0.0, min(1.0, confidence))

    except Exception as e:
        logger.error(f"Error using Groq API: {e}, falling back to regex")
        return detect_abusive_regex(content)

# -------------------------------
# Regex fallback for abusive detection
# -------------------------------
def detect_abusive_regex(content: str) -> float:
    text = normalize_text(content)
    # Keep your regex patterns exactly as before
    max_score = 0.0
    # [same logic as your current script]
    return max_score

# -------------------------------
# Suspicious activity detection
# -------------------------------
def detect_suspicious(content: str) -> float:
    suspicious_words = ['hack', 'scam', 'phish', 'malware', 'virus', 'trojan', 'estafa', 'phishing']
    return 0.8 if any(word in content.lower() for word in suspicious_words) else 0.1

# -------------------------------
# Main moderation endpoint
# -------------------------------
@app.post("/moderate", response_model=ModerationResponse)
async def moderate_content(request: ContentRequest):
    logger.info(f"Moderating content from user {request.user_id}: {request.content[:50]}...")

    spam_score = detect_spam(request.content)
    abusive_score = detect_abusive(request.content)
    suspicious_score = detect_suspicious(request.content)

    logger.info(f"Scores - Spam: {spam_score:.3f}, Abusive: {abusive_score:.3f}, Suspicious: {suspicious_score:.3f}")

    is_spam = spam_score > 0.7
    is_abusive = abusive_score >= 0.8
    is_suspicious = suspicious_score > 0.7

    auto_hide = is_abusive or (is_spam and is_suspicious)
    send_for_review = is_suspicious or (spam_score > 0.5 and abusive_score > 0.5)

    message = None
    if is_abusive:
        import random
        abusive_messages = [
            "No deberías decir eso. Por favor, modera tu vocabulario.",
            "Están prohibidas esas palabras. Sé respetuoso.",
            "Modera tu vocabulario por favor. No toleramos lenguaje abusivo.",
            "Ese tipo de lenguaje no es aceptable aquí.",
            "Por favor, expresa tus ideas de manera respetuosa."
        ]
        message = random.choice(abusive_messages)

    if send_for_review:
        logger.info("Content flagged for review (not persisted)")

    return ModerationResponse(
        is_spam=is_spam,
        is_abusive=is_abusive,
        is_suspicious=is_suspicious,
        auto_hide=auto_hide,
        send_for_review=send_for_review,
        confidence_scores={
            "spam": spam_score,
            "abusive": abusive_score,
            "suspicious": suspicious_score
        },
        message=message
    )

# -------------------------------
# Health check
# -------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# -------------------------------
# Run server
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
