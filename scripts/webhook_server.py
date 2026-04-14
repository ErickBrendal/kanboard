#!/usr/bin/env python3
"""
EBL Kanboard Webhook Server
Flask na porta 5500 — recebe eventos do Kanboard e dispara sync em background
"""

import os
import sys
import hmac
import hashlib
import json
import logging
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ── Carregar .env ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET_TOKEN", "")
PORT           = int(os.getenv("WEBHOOK_PORT", "5500"))
LOG_FILE       = BASE_DIR / "powerbi" / "webhook.log"
SYNC_SCRIPT    = BASE_DIR / "scripts" / "kanboard_to_onedrive.py"

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)

# Estado do sync em background
sync_lock   = threading.Lock()
sync_running = False
last_sync   = None
sync_count  = 0


def run_sync():
    """Executa o script de sync em background (thread separada)."""
    global sync_running, last_sync, sync_count
    with sync_lock:
        if sync_running:
            logger.info("Sync já em execução — ignorando novo disparo")
            return
        sync_running = True

    try:
        logger.info("Iniciando sync Kanboard → OneDrive em background...")
        result = subprocess.run(
            [sys.executable, str(SYNC_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutos máximo
        )
        last_sync = datetime.now().isoformat()
        sync_count += 1

        if result.returncode == 0:
            logger.info(f"Sync #{sync_count} concluído com sucesso")
            # Log das últimas 5 linhas do output
            lines = result.stdout.strip().split("\n")
            for line in lines[-5:]:
                if line.strip():
                    logger.info(f"  {line}")
        else:
            logger.error(f"Sync #{sync_count} falhou (exit code {result.returncode})")
            if result.stderr:
                logger.error(f"  STDERR: {result.stderr[:500]}")

    except subprocess.TimeoutExpired:
        logger.error("Sync expirou (timeout 5 minutos)")
    except Exception as e:
        logger.error(f"Erro ao executar sync: {e}")
    finally:
        with sync_lock:
            sync_running = False


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verifica a assinatura HMAC-SHA256 do Kanboard."""
    if not WEBHOOK_SECRET:
        return True  # Sem secret configurado — aceitar todos
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# ── Rotas ──────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Health check — retorna status do servidor e do último sync."""
    return jsonify({
        "status": "ok",
        "server": "EBL Kanboard Webhook",
        "sync_running": sync_running,
        "last_sync": last_sync,
        "sync_count": sync_count,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """Recebe eventos do Kanboard e dispara sync em background."""
    # Verificar Content-Type
    if not request.is_json:
        logger.warning("Requisição sem Content-Type: application/json")
        return jsonify({"error": "Content-Type must be application/json"}), 400

    # Verificar assinatura (se configurada)
    signature = request.headers.get("X-Kanboard-Signature", "")
    if WEBHOOK_SECRET and signature:
        if not verify_signature(request.data, signature):
            logger.warning("Assinatura inválida — requisição rejeitada")
            return jsonify({"error": "Invalid signature"}), 401

    # Parsear payload
    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"Erro ao parsear JSON: {e}")
        return jsonify({"error": "Invalid JSON"}), 400

    # Log do evento recebido
    event_name = payload.get("event_name", "unknown")
    project_id = payload.get("event_data", {}).get("task", {}).get("project_id", "?")
    logger.info(f"Webhook recebido: event={event_name} project_id={project_id}")

    # Disparar sync em background (thread separada)
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    return jsonify({
        "status": "accepted",
        "event": event_name,
        "sync_triggered": True,
        "timestamp": datetime.now().isoformat(),
    }), 202


@app.route("/sync", methods=["POST"])
def manual_sync():
    """Dispara sync manual (sem autenticação — apenas para uso interno)."""
    logger.info("Sync manual disparado via /sync")
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    return jsonify({
        "status": "accepted",
        "sync_triggered": True,
        "timestamp": datetime.now().isoformat(),
    }), 202


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("EBL Kanboard Webhook Server iniciando")
    logger.info(f"Porta: {PORT}")
    logger.info(f"Script de sync: {SYNC_SCRIPT}")
    logger.info(f"Log: {LOG_FILE}")
    logger.info(f"Secret configurado: {'Sim' if WEBHOOK_SECRET else 'Não'}")
    logger.info("=" * 60)

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        threaded=True,
    )
