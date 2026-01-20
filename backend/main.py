from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from typing import Optional
import unicodedata
import re
import sys
import os

# Add the parent directory to the path to import firebase_confi
# -------------------------------
# Logging setup
# -------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------
# FastAPI app
# -------------------------------
app = FastAPI(title="Content Moderation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://content-moderation-71254.web.app/"],  # Cambiar en producción
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

# -------------------------------
# Normalización de texto
# -------------------------------
def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r'[^\w\s]', ' ', text) 
    text = re.sub(r'\s+', ' ', text)  # Espacios múltiples → 1
    return text


 
# -------------------------------
# Detección de spam
# -------------------------------
def detect_spam(content: str) -> float:
    content_lower = content.lower()

    spam_patterns = {
        'financiero': [
            'gratis', 'dinero', 'dinero fácil', 'gana dinero', 'ingresos pasivos', 'sin esfuerzo',
            'inversión segura', 'retorno garantizado', 'duplicar tu dinero', 'hazte rico',
            'trabaja desde casa', 'oportunidad única', 'sin riesgo', 'ganancias rápidas',
            'criptomonedas gratis', 'bitcoin gratis', 'forex milagroso'
        ],
        'publicitario': [
            'oferta limitada', 'solo hoy', 'último aviso', 'promoción exclusiva',
            'descuento increíble', 'compra ahora', 'haz clic aquí', 'link en bio',
            'visita mi perfil', 'entra aquí', 'no te lo pierdas', 'precio especial', 'imperdible'
        ],
        'afiliados': [
            'sistema probado', 'método secreto', 'fórmula ganadora', 'curso premium gratis',
            'mentor millonario', 'entrenamiento exclusivo', 'masterclass gratuita', 'cupos limitados',
            'resultados garantizados'
        ],
        'phishing': [
            'verifica tu cuenta', 'cuenta suspendida', 'acción requerida', 'confirma tus datos',
            'inicio de sesión urgente', 'problema de seguridad', 'actividad sospechosa',
            'restablecer contraseña', 'soporte técnico'
        ],
        'social': [
            'sígueme', 'follow x follow', 'f4f', 'like por like', 'l4l', 'comenta y gana',
            'comparte para ganar', 'sorteo activo', 'giveaway', 'usuarios reales', 'aumenta seguidores'
        ],
        'generico': [
            'mensaje automático', 'envío masivo', 'no es spam', '100% real', 'totalmente legal',
            'recomendado', 'probado', 'miles de personas', 'éxito asegurado'
        ],
        'evasion': [
            'gr4tis', 'd1nero', 'g@n@ dinero', 'of€rta', 'cl1ck aquí', 'b1tc0in', 'cr1pto'
        ]
    }

    spam_scores = {
        'financiero': 0.9,
        'publicitario': 0.7,
        'afiliados': 0.8,
        'phishing': 1.0,
        'social': 0.6,
        'generico': 0.5,
        'evasion': 0.8
    }

    spam_indicators = {
        'links': ['http', 'https', 'www.', '.com', '.net', '.org', 'link', 'url'],
        'emojis_repetidos': ['💰💰💰', '💡', '🔥🔥🔥', '⭐⭐⭐'],
        'mayusculas_excesivas': lambda text: sum(1 for c in text if c.isupper()) / len(text) > 0.5 if text else False,
        'repetitivo': lambda text: len(set(text.split())) < len(text.split()) * 0.5 if text else False
    }

    max_score = 0.1

    # Patrones de spam
    for category, patterns in spam_patterns.items():
        if any(pattern in content_lower for pattern in patterns):
            max_score = max(max_score, spam_scores[category])

    # Indicadores adicionales
    if any(indicator in content_lower for indicator in spam_indicators['links']):
        max_score = max(max_score, 0.6)
    if any(emoji in content for emoji in spam_indicators['emojis_repetidos']):
        max_score = max(max_score, 0.5)
    if spam_indicators['mayusculas_excesivas'](content):
        max_score = max(max_score, 0.4)
    if spam_indicators['repetitivo'](content):
        max_score = max(max_score, 0.3)

    return max_score

# -------------------------------
# Detección de lenguaje abusivo
# -------------------------------
def detect_abusive(content: str) -> float:
    text = normalize_text(content)

    regex_patterns = {

    # ======================
    # ESPAÑOL
    # ======================

    'insultos_comunes': [
        r't[\s_-]*o[\s_-]*n[\s_-]*t[\s_-]*o[\s_-]*s?',
        r't[\s_-]*o[\s_-]*n[\s_-]*t[\s_-]*i[\s_-]*c[\s_-]*o[\s_-]*s?',
        r'i[\s_-]*d[\s_-]*i[\s_-]*o[\s_-]*t[\s_-]*a[\s_-]*s?',
        r'e[\s_-]*s[\s_-]*t[\s_-]*u[\s_-]*p[\s_-]*i[\s_-]*d[\s_-]*o[\s_-]*s?',
        r'i[\s_-]*m[\s_-]*b[\s_-]*e[\s_-]*c[\s_-]*i[\s_-]*l[\s_-]*e[\s_-]*s?',
        r'r[\s_-]*i[\s_-]*d[\s_-]*i[\s_-]*c[\s_-]*u[\s_-]*l[\s_-]*o[\s_-]*s?'
    ],

    'inutilidad_incapacidad': [
        r'i[\s_-]*n[\s_-]*u[\s_-]*t[\s_-]*i[\s_-]*l[\s_-]*e[\s_-]*s?',
        r'i[\s_-]*n[\s_-]*c[\s_-]*a[\s_-]*p[\s_-]*a[\s_-]*z[\s_-]*e[\s_-]*s?',
        r'i[\s_-]*n[\s_-]*c[\s_-]*o[\s_-]*m[\s_-]*p[\s_-]*e[\s_-]*t[\s_-]*e[\s_-]*n[\s_-]*t[\s_-]*e[\s_-]*s?',
        r'i[\s_-]*n[\s_-]*s[\s_-]*e[\s_-]*r[\s_-]*v[\s_-]*i[\s_-]*b[\s_-]*l[\s_-]*e[\s_-]*s?'
    ],

    'desprecio_humillacion': [
        r'b[\s_-]*a[\s_-]*s[\s_-]*u[\s_-]*r[\s_-]*a',
        r'f[\s_-]*r[\s_-]*a[\s_-]*c[\s_-]*a[\s_-]*s[\s_-]*o',
        r'd[\s_-]*a[\s_-]*s[\s_-]*\s*p[\s_-]*e[\s_-]*n[\s_-]*a',
        r'v[\s_-]*e[\s_-]*r[\s_-]*g[\s_-]*u[\s_-]*e[\s_-]*n[\s_-]*z[\s_-]*o[\s_-]*s?'
    ],

    'deshumanizacion': [
        r'n[\s_-]*o[\s_-]*\s*v[\s_-]*a[\s_-]*l[\s_-]*e[\s_-]*s?\s+n[\s_-]*a[\s_-]*d[\s_-]*a',
        r'n[\s_-]*a[\s_-]*d[\s_-]*a\s+e[\s_-]*r[\s_-]*e[\s_-]*s?',
        r'c[\s_-]*e[\s_-]*r[\s_-]*o',
        r'e[\s_-]*s[\s_-]*t[\s_-]*o[\s_-]*r[\s_-]*b[\s_-]*o'
    ],

    'rechazo_exclusion': [
        r'v[\s_-]*e[\s_-]*t[\s_-]*e\s+d[\s_-]*e\s+a[\s_-]*q[\s_-]*u[\s_-]*i',
        r'n[\s_-]*o\s+e[\s_-]*r[\s_-]*e[\s_-]*s?\s+b[\s_-]*i[\s_-]*e[\s_-]*n[\s_-]*v[\s_-]*e[\s_-]*n[\s_-]*i[\s_-]*d[\s_-]*o',
        r'a[\s_-]*q[\s_-]*u[\s_-]*i\s+n[\s_-]*o\s+t[\s_-]*e\s+q[\s_-]*u[\s_-]*e[\s_-]*r[\s_-]*e[\s_-]*m[\s_-]*o[\s_-]*s'
    ],

    'amenaza_velada': [
        r'v[\s_-]*a[\s_-]*s?\s+a\s+a[\s_-]*r[\s_-]*r[\s_-]*e[\s_-]*p[\s_-]*e[\s_-]*n[\s_-]*t[\s_-]*i[\s_-]*r[\s_-]*t[\s_-]*e',
        r'n[\s_-]*o\s+t[\s_-]*e\s+v[\s_-]*a\s+a\s+s[\s_-]*a[\s_-]*l[\s_-]*i[\s_-]*r\s+g[\s_-]*r[\s_-]*a[\s_-]*t[\s_-]*i[\s_-]*s',
        r'v[\s_-]*a[\s_-]*s?\s+a\s+p[\s_-]*a[\s_-]*g[\s_-]*a[\s_-]*r'
    ],

    'imperativos_agresivos': [
        r'c[\s_-]*a[\s_-]*l[\s_-]*l[\s_-]*a[\s_-]*t[\s_-]*e',
        r'l[\s_-]*a[\s_-]*r[\s_-]*g[\s_-]*a[\s_-]*t[\s_-]*e',
        r'd[\s_-]*e[\s_-]*j[\s_-]*a\s+d[\s_-]*e\s+h[\s_-]*a[\s_-]*b[\s_-]*l[\s_-]*a[\s_-]*r'
    ],

    # ======================
    # CONTEXTO
    # ======================

     'contextual': [
    r'\beres\s+(un\s+)?(estupido|tonto|idiota|imbecil|basura|ridiculo)\b',
    r'\bestás\s+(un\s+)?(estupido|tonto|idiota|imbecil|basura|ridiculo)\b'
        ],

    'repeticion_abusiva': [
        r'\b(\w+)\b(?:\s+\1){2,}'
    ],

    # ======================
    # INGLÉS
    # ======================

    'english_harassment': [
        r'f[\s_-]*u[\s_-]*c[\s_-]*k[\s_-]*\s*o[\s_-]*f[\s_-]*f',
        r's[\s_-]*h[\s_-]*u[\s_-]*t[\s_-]*\s*u[\s_-]*p'
    ],

    'english_insults': [
        r's[\s_-]*h[\s_-]*i[\s_-]*t',
        r'd[\s_-]*a[\s_-]*m[\s_-]*n',
        r'b[\s_-]*i[\s_-]*t[\s_-]*c[\s_-]*h',
        r'a[\s_-]*s[\s_-]*s[\s_-]*h[\s_-]*o[\s_-]*l[\s_-]*e',
        r'b[\s_-]*a[\s_-]*s[\s_-]*t[\s_-]*a[\s_-]*r[\s_-]*d',
        r's[\s_-]*t[\s_-]*u[\s_-]*p[\s_-]*i[\s_-]*d',
        r'i[\s_-]*d[\s_-]*i[\s_-]*o[\s_-]*t',
        r'm[\s_-]*o[\s_-]*r[\s_-]*o[\s_-]*n',
        r'd[\s_-]*u[\s_-]*m[\s_-]*b[\s_-]*a[\s_-]*s[\s_-]*s',
        r'l[\s_-]*o[\s_-]*s[\s_-]*e[\s_-]*r'
    ],
  


}


    regex_scores = {cat: 0.8 for cat in regex_patterns}
    regex_scores.update({
        'english_harassment': 0.85,
        'english_insults': 0.8,
        'deshumanizacion': 0.9,  # Alto peso
        'contextual': 0.8,  # Muy efectivo
        'repeticion_abusiva': 0.8,
        'amenaza_velada': 0.8,
        'imperativos_agresivos': 0.8, 
        'rechazo_exclusion': 0.8 ,
        'deshumanizacion': 0.8, 
        'inutilidad_incapacidad':0.8,
        'insultos_comunes': 0.8
    })
  
    max_score = 0.0
    match_count = 0

    for category, patterns in regex_patterns.items():
         category_score = regex_scores.get(category, 0.0)
         if category_score < 0.8:
            continue
         for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                logger.info(f"Matched pattern '{pat}' in category '{category}'")
                max_score = max(max_score,  regex_scores[category])
                match_count += 1

    # Bonus por múltiples matches
    if match_count > 1:
        max_score = min(max_score + 0.2, 1.0)

    return max_score

# -------------------------------
# Detección de actividad sospechosa
# -------------------------------
def detect_suspicious(content: str) -> float:
    suspicious_words = ['hack', 'scam', 'phish', 'malware', 'virus', 'trojan', 'estafa', 'phishing']
    return 0.8 if any(word in content.lower() for word in suspicious_words) else 0.1

# -------------------------------
# Endpoint principal
# -------------------------------
@app.post("/moderate", response_model=ModerationResponse)
async def moderate_content(request: ContentRequest):
    logger.info(f"Moderating content from user {request.user_id}: {request.content[:50]}...")

    spam_score = detect_spam(request.content)
    abusive_score = detect_abusive(request.content)
    suspicious_score = detect_suspicious(request.content)

    logger.info(f"Scores - Spam: {spam_score:.3f}, Abusive: {abusive_score:.3f}, Suspicious: {suspicious_score:.3f}")

    # Thresholds
    is_spam = spam_score > 0.7
    is_abusive = abusive_score >= 0.8
    is_suspicious = suspicious_score > 0.7

    auto_hide = is_abusive or (is_spam and is_suspicious)
    send_for_review = is_suspicious or (spam_score > 0.5 and abusive_score > 0.5)

    # Flag in database if needed
    if send_for_review:
        try:
            doc_ref = db.collection('moderation_queue').document()
            doc_ref.set({
                'content': request.content,
                'user_id': request.user_id,
                'spam_score': spam_score,
                'abusive_score': abusive_score,
                'suspicious_score': suspicious_score,
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Content flagged for review and stored in Firestore")
        except Exception as e:
            logger.error(f"Failed to store in Firestore: {e}")

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
        }
    )

# -------------------------------
# Health check
# -------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
