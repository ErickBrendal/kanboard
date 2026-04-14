#!/usr/bin/env python3
"""
EBL Kanboard Webhook — Monitor e Alerta de Falha
=================================================
Verifica se o serviço kanboard-webhook está ativo e envia
alerta por e-mail via SMTP do Microsoft 365 quando inativo.

Modos de uso:
  python3 alert_webhook.py                  # watchdog: verifica e alerta se inativo
  python3 alert_webhook.py --trigger systemd-failure  # chamado pelo systemd OnFailure
  python3 alert_webhook.py --test           # envia e-mail de teste
"""

import os
import sys
import subprocess
import smtplib
import socket
import json
import argparse
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
ENV_FILE   = BASE_DIR / ".env"
LOG_FILE   = BASE_DIR / "powerbi" / "alert.log"
STATE_FILE = BASE_DIR / "powerbi" / "alert_state.json"

SERVICE_NAME = "kanboard-webhook"
HEALTH_URL   = "http://localhost:5500/health"

# Destinatários do alerta (separados por vírgula no .env ou lista padrão)
DEFAULT_RECIPIENTS = ["admebl@eblsolucoescorporativas.com"]

# SMTP Microsoft 365
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587


# ── Utilitários ───────────────────────────────────────────────────────────────

def load_env():
    """Carrega variáveis do .env sem dependência de python-dotenv."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    # Mescla com os já definidos no ambiente do processo
    for k, v in env.items():
        os.environ.setdefault(k, v)
    return env


def log(level: str, msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"last_alert_sent": None, "consecutive_failures": 0, "last_ok": None}


def save_state(state: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        log("WARN", f"Não foi possível salvar estado: {e}")


# ── Verificação do serviço ────────────────────────────────────────────────────

def check_service_systemd() -> tuple[bool, str]:
    """Retorna (ativo, mensagem)."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True, timeout=10
        )
        active = result.stdout.strip() == "active"
        return active, result.stdout.strip()
    except Exception as e:
        return False, f"Erro ao verificar systemd: {e}"


def check_service_http() -> tuple[bool, str]:
    """Verifica o health endpoint HTTP."""
    try:
        import urllib.request
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok", json.dumps(data)
    except Exception as e:
        return False, f"Health check falhou: {e}"


def get_service_details() -> dict:
    """Coleta detalhes do serviço para o e-mail de alerta."""
    details = {
        "hostname": socket.gethostname(),
        "ip_publico": os.environ.get("VM_IP", "150.230.88.196"),
        "timestamp": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC"),
        "systemd_status": "desconhecido",
        "ultimas_linhas_log": "",
        "uptime_vm": "",
    }

    # Status detalhado do systemd
    try:
        r = subprocess.run(
            ["systemctl", "status", SERVICE_NAME, "--no-pager", "-l"],
            capture_output=True, text=True, timeout=10
        )
        details["systemd_status"] = r.stdout[:800]
    except Exception:
        pass

    # Últimas linhas do log do serviço
    try:
        r = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", "20", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        details["ultimas_linhas_log"] = r.stdout[-1200:]
    except Exception:
        pass

    # Uptime da VM
    try:
        r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        details["uptime_vm"] = r.stdout.strip()
    except Exception:
        pass

    return details


# ── Envio de e-mail ───────────────────────────────────────────────────────────

def send_alert_email(subject: str, details: dict, is_recovery: bool = False):
    """Envia e-mail de alerta ou recuperação via SMTP Microsoft 365."""
    smtp_user = os.environ.get("PBI_USERNAME", "admebl@eblsolucoescorporativas.com")
    smtp_pass = os.environ.get("AZURE_CLIENT_SECRET", "")

    # Tentar obter senha de e-mail dedicada, se configurada
    smtp_pass = os.environ.get("SMTP_PASSWORD", smtp_pass)

    recipients_raw = os.environ.get("ALERT_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()] \
                 if recipients_raw else DEFAULT_RECIPIENTS

    color_header = "#27ae60" if is_recovery else "#c0392b"
    icon = "✅" if is_recovery else "🚨"
    status_label = "RECUPERADO" if is_recovery else "INATIVO"

    html_body = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
  <div style="max-width:640px; margin:auto; background:#fff; border-radius:8px;
              box-shadow:0 2px 8px rgba(0,0,0,.1); overflow:hidden;">

    <!-- Cabeçalho -->
    <div style="background:{color_header}; padding:24px 32px;">
      <h1 style="margin:0; color:#fff; font-size:22px;">
        {icon} Serviço {status_label}: <code>kanboard-webhook</code>
      </h1>
      <p style="margin:6px 0 0; color:rgba(255,255,255,.85); font-size:14px;">
        EBL Soluções Corporativas — Monitoramento Automático
      </p>
    </div>

    <!-- Corpo -->
    <div style="padding:28px 32px;">
      <table style="width:100%; border-collapse:collapse; font-size:14px;">
        <tr>
          <td style="padding:8px 0; color:#666; width:160px;"><strong>Servidor</strong></td>
          <td style="padding:8px 0;">{details['hostname']} ({details['ip_publico']})</td>
        </tr>
        <tr style="background:#f9f9f9;">
          <td style="padding:8px 0; color:#666;"><strong>Data/Hora</strong></td>
          <td style="padding:8px 0;">{details['timestamp']}</td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#666;"><strong>Uptime VM</strong></td>
          <td style="padding:8px 0;">{details.get('uptime_vm', 'N/A')}</td>
        </tr>
      </table>

      <h3 style="margin:24px 0 8px; font-size:15px; color:#333;">
        Status do Serviço (systemd)
      </h3>
      <pre style="background:#1e1e1e; color:#d4d4d4; padding:16px; border-radius:6px;
                  font-size:12px; overflow-x:auto; white-space:pre-wrap;">{details['systemd_status']}</pre>

      <h3 style="margin:24px 0 8px; font-size:15px; color:#333;">
        Últimas Linhas do Log
      </h3>
      <pre style="background:#1e1e1e; color:#d4d4d4; padding:16px; border-radius:6px;
                  font-size:12px; overflow-x:auto; white-space:pre-wrap;">{details['ultimas_linhas_log']}</pre>

      {"" if is_recovery else """
      <div style="background:#fff3cd; border-left:4px solid #f0ad4e; padding:14px 18px;
                  margin-top:20px; border-radius:4px;">
        <strong>Ação Recomendada:</strong><br>
        O serviço tentará se recuperar automaticamente (systemd Restart=always).<br>
        Se o problema persistir, conecte-se à VM e execute:<br>
        <code style="background:#f8f8f8; padding:2px 6px; border-radius:3px;">
          sudo systemctl restart kanboard-webhook
        </code>
      </div>
      """}
    </div>

    <!-- Rodapé -->
    <div style="background:#f0f0f0; padding:14px 32px; font-size:12px; color:#888;">
      Alerta gerado automaticamente pelo watchdog EBL Kanboard Monitor.<br>
      VM Oracle Cloud — {details['ip_publico']} — Região sa-saopaulo-1
    </div>
  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_bytes())
        log("INFO", f"E-mail de alerta enviado para: {', '.join(recipients)}")
        return True
    except Exception as e:
        log("ERROR", f"Falha ao enviar e-mail via SMTP: {e}")
        # Fallback: registrar no log do webhook para visibilidade
        try:
            fallback_log = BASE_DIR / "powerbi" / "webhook.log"
            with fallback_log.open("a") as f:
                f.write(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}]"
                        f" [ALERT] {subject}\n")
        except Exception:
            pass
        return False


# ── Lógica principal ──────────────────────────────────────────────────────────

def run_watchdog(trigger: str = "cron"):
    """Verifica o serviço e envia alerta se necessário."""
    load_env()
    state = load_state()

    systemd_ok, systemd_msg = check_service_systemd()
    http_ok, http_msg       = check_service_http()

    service_ok = systemd_ok and http_ok

    now_iso = datetime.now(timezone.utc).isoformat()

    if service_ok:
        if state.get("consecutive_failures", 0) > 0:
            # Serviço se recuperou — enviar e-mail de recuperação
            log("INFO", "Serviço recuperado. Enviando notificação de recuperação.")
            details = get_service_details()
            send_alert_email(
                subject=f"✅ [EBL] Serviço kanboard-webhook RECUPERADO — {details['hostname']}",
                details=details,
                is_recovery=True
            )
        else:
            log("INFO", f"Serviço OK (systemd: {systemd_msg}, http: {http_ok})")

        state["consecutive_failures"] = 0
        state["last_ok"] = now_iso
        save_state(state)
        return 0

    # Serviço inativo
    state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
    log("WARN", f"Serviço INATIVO! Falha #{state['consecutive_failures']} "
                f"(systemd: {systemd_msg}, http: {http_ok}, trigger: {trigger})")

    # Evitar spam: aguardar pelo menos 2 falhas consecutivas antes de alertar
    # (exceto quando chamado pelo systemd OnFailure, que alerta imediatamente)
    min_failures = 1 if trigger == "systemd-failure" else 2
    last_alert   = state.get("last_alert_sent")
    cooldown_min = 30  # minutos entre alertas repetidos

    should_alert = (
        state["consecutive_failures"] >= min_failures
        and (
            last_alert is None
            or (datetime.now(timezone.utc) -
                datetime.fromisoformat(last_alert)).total_seconds() > cooldown_min * 60
        )
    )

    if should_alert:
        details = get_service_details()
        hostname = details["hostname"]
        subject = (
            f"🚨 [EBL] Serviço kanboard-webhook INATIVO — {hostname} "
            f"(falha #{state['consecutive_failures']})"
        )
        sent = send_alert_email(subject=subject, details=details, is_recovery=False)
        if sent:
            state["last_alert_sent"] = now_iso
    else:
        log("INFO", f"Alerta suprimido (cooldown ou falhas insuficientes: "
                    f"{state['consecutive_failures']}/{min_failures})")

    save_state(state)
    return 1


def run_test():
    """Envia um e-mail de teste para validar a configuração SMTP."""
    load_env()
    log("INFO", "Enviando e-mail de TESTE...")
    details = get_service_details()
    details["systemd_status"] = "** ESTE É UM E-MAIL DE TESTE **\nNenhuma falha real ocorreu."
    details["ultimas_linhas_log"] = "Teste de conectividade SMTP — EBL Kanboard Monitor"
    sent = send_alert_email(
        subject=f"🔔 [EBL] Teste de alerta kanboard-webhook — {details['hostname']}",
        details=details,
        is_recovery=False
    )
    return 0 if sent else 1


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EBL Kanboard Webhook Monitor")
    parser.add_argument("--trigger", default="cron",
                        help="Origem do disparo: cron | systemd-failure | manual")
    parser.add_argument("--test", action="store_true",
                        help="Envia e-mail de teste e sai")
    args = parser.parse_args()

    if args.test:
        sys.exit(run_test())
    else:
        sys.exit(run_watchdog(trigger=args.trigger))
