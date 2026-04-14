#!/usr/bin/env python3
"""
Script para:
1. Adicionar permissões Files.Read.All e Sites.Read.All ao App Registration via Graph API
2. Descobrir o Drive ID do OneDrive do usuário admebl@eblsolucoescorporativas.com
"""
import json
import requests

# Configurações
TENANT_ID = "208364c6-eee7-4324-ac4a-d45fe452a1bd"
CLIENT_ID = "876e9f44-d589-49ed-b4b1-239bbd2430a0"
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
APP_OBJECT_ID = CLIENT_ID  # Será resolvido

# Passo 1: Obter token com permissões de admin (usando client_credentials)
print("=" * 60)
print("PASSO 1: Obtendo token de acesso...")
token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
token_data = {
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": "https://graph.microsoft.com/.default"
}
resp = requests.post(token_url, data=token_data)
if resp.status_code != 200:
    print(f"ERRO ao obter token: {resp.status_code} - {resp.text}")
    exit(1)

token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print(f"Token obtido com sucesso! (primeiros 50 chars: {token[:50]}...)")

# Passo 2: Buscar o Object ID do App Registration
print("\n" + "=" * 60)
print("PASSO 2: Buscando Object ID do App Registration...")
app_resp = requests.get(
    f"https://graph.microsoft.com/v1.0/applications?$filter=appId eq '{CLIENT_ID}'",
    headers=headers
)
print(f"Status: {app_resp.status_code}")
if app_resp.status_code == 200:
    apps = app_resp.json().get("value", [])
    if apps:
        APP_OBJECT_ID = apps[0]["id"]
        print(f"Object ID encontrado: {APP_OBJECT_ID}")
        print(f"Display Name: {apps[0].get('displayName')}")
        # Listar permissões atuais
        current_perms = apps[0].get("requiredResourceAccess", [])
        print(f"Permissões atuais: {len(current_perms)} recursos")
        for rra in current_perms:
            print(f"  Resource: {rra.get('resourceAppId')}")
            for ra in rra.get("resourceAccess", []):
                print(f"    - {ra.get('id')} ({ra.get('type')})")
    else:
        print("App não encontrado!")
else:
    print(f"Erro: {app_resp.text}")

# Passo 3: Adicionar permissões Files.Read.All e Sites.Read.All (Application)
# IDs conhecidos do Microsoft Graph:
# Files.Read.All (Application): 01d4889c-1287-42c6-ac1f-5d1e02578ef6
# Sites.Read.All (Application): 332a536c-c7ef-4017-ab91-336970924f0d
# Files.ReadWrite.All (Application): 75359482-378d-4052-8f01-80520e7db3cd
print("\n" + "=" * 60)
print("PASSO 3: Adicionando permissões Files.Read.All e Sites.Read.All...")

GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
FILES_READ_ALL_ID = "01d4889c-1287-42c6-ac1f-5d1e02578ef6"
SITES_READ_ALL_ID = "332a536c-c7ef-4017-ab91-336970924f0d"

# Construir payload com permissões existentes + novas
new_perms = {
    "requiredResourceAccess": [
        {
            "resourceAppId": GRAPH_APP_ID,
            "resourceAccess": [
                {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},  # User.Read (existente)
                {"id": FILES_READ_ALL_ID, "type": "Role"},   # Files.Read.All (Application)
                {"id": SITES_READ_ALL_ID, "type": "Role"},   # Sites.Read.All (Application)
            ]
        }
    ]
}

update_resp = requests.patch(
    f"https://graph.microsoft.com/v1.0/applications/{APP_OBJECT_ID}",
    headers=headers,
    json=new_perms
)
print(f"Status da atualização: {update_resp.status_code}")
if update_resp.status_code == 204:
    print("Permissões adicionadas com sucesso!")
else:
    print(f"Resposta: {update_resp.text}")

# Passo 4: Listar usuários para encontrar o UPN correto
print("\n" + "=" * 60)
print("PASSO 4: Listando usuários do tenant...")
users_resp = requests.get(
    "https://graph.microsoft.com/v1.0/users?$select=id,displayName,userPrincipalName&$top=10",
    headers=headers
)
print(f"Status: {users_resp.status_code}")
if users_resp.status_code == 200:
    users = users_resp.json().get("value", [])
    for u in users:
        print(f"  {u.get('displayName')} | {u.get('userPrincipalName')} | {u.get('id')}")
    # Salvar IDs para uso posterior
    with open("/tmp/users_list.json", "w") as f:
        json.dump(users, f, indent=2)
else:
    print(f"Erro: {users_resp.text}")

# Passo 5: Tentar obter Drive ID do usuário admebl
print("\n" + "=" * 60)
print("PASSO 5: Buscando Drive ID do OneDrive...")
target_upn = "admebl@eblsolucoescorporativas.com"

# Tentar pelo UPN diretamente
drive_resp = requests.get(
    f"https://graph.microsoft.com/v1.0/users/{target_upn}/drive",
    headers=headers
)
print(f"Status (drive por UPN): {drive_resp.status_code}")
if drive_resp.status_code == 200:
    drive = drive_resp.json()
    print(f"Drive ID: {drive.get('id')}")
    print(f"Drive Type: {drive.get('driveType')}")
    print(f"Drive Name: {drive.get('name')}")
    print(f"Owner: {drive.get('owner', {}).get('user', {}).get('displayName')}")
    with open("/tmp/drive_info.json", "w") as f:
        json.dump(drive, f, indent=2)
    # Atualizar azure_config.json
    with open("/tmp/azure_config.json", "r") as f:
        config = json.load(f)
    config["drive_id"] = drive.get("id")
    config["drive_type"] = drive.get("driveType")
    config["drive_name"] = drive.get("name")
    with open("/tmp/azure_config.json", "w") as f:
        json.dump(config, f, indent=2)
    print("\nDrive ID salvo em /tmp/azure_config.json!")
else:
    print(f"Erro: {drive_resp.text}")
    # Tentar listar drives
    drives_resp = requests.get(
        f"https://graph.microsoft.com/v1.0/users/{target_upn}/drives",
        headers=headers
    )
    print(f"Status (drives list): {drives_resp.status_code}")
    print(f"Resposta: {drives_resp.text[:500]}")

print("\n" + "=" * 60)
print("CONCLUÍDO!")
