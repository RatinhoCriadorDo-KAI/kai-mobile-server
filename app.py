
import os
import time
from collections import defaultdict, deque

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
APP_TOKEN = os.environ.get("KAI_APP_TOKEN", "")

MODEL = "openrouter/free"

# Limite simples por endereço IP, armazenado em memória.
requests_by_ip = defaultdict(deque)
MAX_REQUESTS = 10
WINDOW_SECONDS = 60


@app.get("/")
def home():
    return jsonify({
        "app": "K.A.I MOBILE",
        "status": "online"
    })


@app.post("/api/chat")
def chat():
    if not API_KEY or not APP_TOKEN:
        return jsonify({"error": "Servidor não configurado."}), 503

    supplied_token = request.headers.get("X-KAI-Token", "")
    if supplied_token != APP_TOKEN:
        return jsonify({"error": "Acesso não autorizado."}), 401

    ip = request.remote_addr or "unknown"
    now = time.time()
    history = requests_by_ip[ip]

    while history and now - history[0] > WINDOW_SECONDS:
        history.popleft()

    if len(history) >= MAX_REQUESTS:
        return jsonify({
            "error": "Muitas mensagens. Tente novamente em um minuto."
        }), 429

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Envie JSON válido."}), 400

    message = data.get("message")
    if not isinstance(message, str):
        return jsonify({"error": "Mensagem inválida."}), 400

    message = message.strip()
    if not message or len(message) > 2000:
        return jsonify({
            "error": "A mensagem deve ter de 1 a 2000 caracteres."
        }), 400

    history.append(now)

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "X-Title": "K.A.I MOBILE"
            },
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Você é K.A.I, um assistente prestativo. "
                            "Responda em português brasileiro, com clareza."
                        )
                    },
                    {"role": "user", "content": message}
                ]
            },
            timeout=45
        )
        response.raise_for_status()
        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        return jsonify({"answer": answer or "Não consegui gerar uma resposta."})

    except requests.RequestException:
        app.logger.warning("Falha na comunicação com o provedor de IA.")
        return jsonify({
            "error": "A IA está indisponível no momento. Tente novamente."
        }), 502
    except (KeyError, IndexError, TypeError, ValueError):
        return jsonify({
            "error": "A resposta da IA veio em formato inesperado."
        }), 502
