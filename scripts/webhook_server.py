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
import requests
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

# ── Credenciais Power BI ───────────────────────────────────────────────────────
PBI_TENANT_ID     = os.getenv("PBI_TENANT_ID", "")
PBI_CLIENT_ID     = os.getenv("PBI_CLIENT_ID", "")
PBI_CLIENT_SECRET = os.getenv("PBI_CLIENT_SECRET", "")

# IDs dos datasets a serem atualizados após cada sync
PBI_DATASET_IDS = [
    os.getenv("PBI_DATASET_ID", "58672f66-ef95-476f-bb0e-2b856a93298d"),  # EBL Kanboard Demandas
    "b7ee61f3-937d-438c-a671-f29045a0a782",  # EBL Portfolio TI Elgin
]

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
sync_lock        = threading.Lock()
sync_running     = False
last_sync        = None
sync_count       = 0
last_pbi_refresh = None
pbi_refresh_count = 0


# ── Power BI Refresh ───────────────────────────────────────────────────────────

def get_pbi_token() -> str:
    """Obtém token de acesso ao Power BI via client_credentials (Service Principal)."""
    url = f"https://login.microsoftonline.com/{PBI_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     PBI_CLIENT_ID,
        "client_secret": PBI_CLIENT_SECRET,
        "scope":         "https://analysis.windows.net/powerbi/api/.default",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _refresh_via_user(dataset_id: str):
    """Fallback: dispara refresh via token de usuário (ROPC flow)."""
    username = os.getenv("PBI_USERNAME", "")
    password = os.getenv("PBI_PASSWORD", "")
    if not username or not password:
        logger.warning(f"  PBI_USERNAME/PBI_PASSWORD não configurados — refresh via usuário ignorado para {dataset_id}")
        return
    try:
        url_token = f"https://login.microsoftonline.com/{PBI_TENANT_ID}/oauth2/v2.0/token"
        data = {
            "grant_type":    "password",
            "client_id":     PBI_CLIENT_ID,
            "client_secret": PBI_CLIENT_SECRET,
            "scope":         "https://analysis.windows.net/powerbi/api/.default",
            "username":      username,
            "password":      password,
        }
        resp = requests.post(url_token, data=data, timeout=30)
        resp.raise_for_status()
        token = resp.json()["access_token"]
        url_refresh = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/refreshes"
        r = requests.post(
            url_refresh,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"notifyOption": "NoNotification"},
            timeout=30,
        )
        if r.status_code in (200, 202):
            logger.info(f"  ✓ Refresh via usuário disparado — dataset {dataset_id} (HTTP {r.status_code})")
        else:
            logger.warning(f"  ✗ Refresh via usuário falhou — dataset {dataset_id} (HTTP {r.status_code}): {r.text[:200]}")
    except Exception as e:
        logger.error(f"  ✗ Erro no refresh via usuário para {dataset_id}: {e}")


def refresh_powerbi():
    """Dispara refresh nos datasets do Power BI após sync bem-sucedido."""
    global last_pbi_refresh, pbi_refresh_count

    if not PBI_TENANT_ID or not PBI_CLIENT_ID or not PBI_CLIENT_SECRET:
        logger.warning("Credenciais PBI não configuradas — refresh ignorado")
        return

    logger.info("Disparando refresh automático nos datasets do Power BI...")
    try:
        token = get_pbi_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
        success_count = 0
        for dataset_id in PBI_DATASET_IDS:
            if not dataset_id:
                continue
            url = f"https://api.powerbi.com/v1.0/myorg/datasets/{dataset_id}/refreshes"
            try:
                resp = requests.post(
                    url, headers=headers,
                    json={"notifyOption": "NoNotification"},
                    timeout=30,
                )
                if resp.status_code in (200, 202):
                    logger.info(f"  ✓ Refresh disparado — dataset {dataset_id} (HTTP {resp.status_code})")
                    success_count += 1
                elif resp.status_code == 403:
                    logger.warning(f"  SP sem permissão para {dataset_id} — tentando via usuário...")
                    _refresh_via_user(dataset_id)
                    success_count += 1
                else:
                    logger.warning(f"  ✗ Refresh falhou — dataset {dataset_id} (HTTP {resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                logger.error(f"  ✗ Erro ao disparar refresh dataset {dataset_id}: {e}")

        if success_count > 0:
            last_pbi_refresh = datetime.now().isoformat()
            pbi_refresh_count += 1
            logger.info(f"Power BI refresh #{pbi_refresh_count} concluído — {success_count}/{len(PBI_DATASET_IDS)} datasets")
    except Exception as e:
        logger.error(f"Erro ao obter token Power BI: {e}")
        for dataset_id in PBI_DATASET_IDS:
            if dataset_id:
                _refresh_via_user(dataset_id)


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
            # ── Disparar refresh automático no Power BI ────────────────────
            refresh_powerbi()
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
        "status":            "ok",
        "server":            "EBL Kanboard Webhook",
        "sync_running":      sync_running,
        "last_sync":         last_sync,
        "sync_count":        sync_count,
        "last_pbi_refresh":  last_pbi_refresh,
        "pbi_refresh_count": pbi_refresh_count,
        "timestamp":         datetime.now().isoformat(),
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


@app.route("/refresh-pbi", methods=["POST"])
def manual_pbi_refresh():
    """Dispara refresh manual do Power BI sem sync do Kanboard."""
    logger.info("Refresh manual do Power BI disparado via /refresh-pbi")
    thread = threading.Thread(target=refresh_powerbi, daemon=True)
    thread.start()
    return jsonify({
        "status":            "accepted",
        "refresh_triggered": True,
        "timestamp":         datetime.now().isoformat(),
    }), 202


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("EBL Kanboard Webhook Server iniciando")
    logger.info(f"Porta: {PORT}")
    logger.info(f"Script de sync: {SYNC_SCRIPT}")
    logger.info(f"Log: {LOG_FILE}")
    logger.info(f"Secret configurado: {'Sim' if WEBHOOK_SECRET else 'Não'}")
    logger.info(f"Power BI datasets: {[d for d in PBI_DATASET_IDS if d]}")
    logger.info("=" * 60)

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        threaded=True,
    )
