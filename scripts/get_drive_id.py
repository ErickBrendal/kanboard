#!/usr/bin/env python3
"""
Obtém token via client_credentials e descobre o Drive ID do OneDrive do usuário admebl.
"""
import requests
import os
import json

TENANT_ID = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
CLIENT_ID = "876e9f44-d589-49ed-b4b1-239bbd2430a0"
CLIENT_SECRET = os.environ.get("PBI_CLIENT_SECRET", "")  # Definir via variável de ambiente
USER_UPN = "admebl@eblsolucoescorporativas.com"

print("=== Obtendo token via client_credentials ===")
token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
token_data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "https://graph.microsoft.com/.default",
    "grant_type": "client_credentials"
}

resp = requests.post(token_url, data=token_data)
token_json = resp.json()

if "error" in token_json:
    print(f"ERRO ao obter token: {token_json['error']}")
    print(f"Descrição: {token_json.get('error_description','')[:300]}")
    exit(1)

access_token = token_json["access_token"]
print(f"Token obtido com sucesso! (length: {len(access_token)})")

headers = {"Authorization": f"Bearer {access_token}"}

print(f"\n=== Buscando Drive principal do usuário {USER_UPN} ===")
drive_resp = requests.get(
    f"https://graph.microsoft.com/v1.0/users/{USER_UPN}/drive",
    headers=headers
)
drive_json = drive_resp.json()

if "error" in drive_json:
    print(f"ERRO: {drive_json['error']['message']}")
else:
    print(f"Drive ID:   {drive_json.get('id')}")
    print(f"Drive Type: {drive_json.get('driveType')}")
    print(f"Nome:       {drive_json.get('name')}")
    print(f"Quota:      {drive_json.get('quota', {}).get('used', 0) // 1024 // 1024} MB usados")

print(f"\n=== Listando todos os drives do usuário ===")
drives_resp = requests.get(
    f"https://graph.microsoft.com/v1.0/users/{USER_UPN}/drives",
    headers=headers
)
drives_json = drives_resp.json()

if "error" in drives_json:
    print(f"ERRO: {drives_json['error']['message']}")
else:
    for d in drives_json.get("value", []):
        print(f"  ID: {d.get('id')} | Tipo: {d.get('driveType')} | Nome: {d.get('name')}")

# Salvar resultado
result = {
    "drive_id": drive_json.get("id"),
    "drive_type": drive_json.get("driveType"),
    "drive_name": drive_json.get("name"),
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "tenant_id": TENANT_ID,
    "secret_id": "376233d3-4228-43bc-858e-04d9cbb1b70c",
    "secret_description": "EBL-Kanboard-PowerBI-Sync",
    "secret_expires": "2026-10-11"
}

with open("/tmp/azure_config.json", "w") as f:
    json.dump(result, f, indent=2)

print(f"\n=== Resultado salvo em /tmp/azure_config.json ===")
print(json.dumps(result, indent=2))
