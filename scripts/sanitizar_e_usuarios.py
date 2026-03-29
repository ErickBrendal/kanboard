#!/usr/bin/env python3
"""
Script de Sanitização Completa e Gestão de Usuários — Kanboard EBL
Especialistas: Arquiteto de Projetos + Especialista em UX + Analista de Dados
"""
import requests, json, time

BASE = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH = ("admin", "Senha@2026")

def api(method, params={}):
    try:
        r = requests.post(BASE, auth=AUTH,
            json={"jsonrpc":"2.0","method":method,"id":1,"params":params},
            timeout=15)
        return r.json().get("result")
    except Exception as e:
        print(f"  ⚠️  Erro API [{method}]: {e}")
        return None

print("=" * 60)
print("  SANITIZAÇÃO COMPLETA — KANBOARD EBL")
print("  Especialistas: Arquiteto + UX + Dados")
print("=" * 60)

# ============================================================
# 1. CRIAR USUÁRIOS DA EQUIPE COMPLETA
# ============================================================
print("\n[1/4] CRIANDO USUÁRIOS DA EQUIPE...")

usuarios = [
    {
        "username": "marcio.souza",
        "name": "Marcio Souza",
        "email": "marcio.souza@eblsolucoescorporativas.com",
        "role": "app-manager",
        "password": "EBL@Marcio2026"
    },
    {
        "username": "elder.rodrigues",
        "name": "Elder Rodrigues",
        "email": "elder.rodrigues@eblsolucoescorporativas.com",
        "role": "app-manager",
        "password": "EBL@Elder2026"
    },
    {
        "username": "felipe.nascimento",
        "name": "Felipe Nascimento",
        "email": "felipe.nascimento@eblsolucoescorporativas.com",
        "role": "app-user",
        "password": "EBL@Felipe2026"
    },
    {
        "username": "carlos.almeida",
        "name": "Carlos Almeida",
        "email": "carlos.almeida@eblsolucoescorporativas.com",
        "role": "app-user",
        "password": "EBL@Carlos2026"
    },
    {
        "username": "erick.almeida",
        "name": "Erick Almeida",
        "email": "erick.almeida@eblsolucoescorporativas.com",
        "role": "app-manager",
        "password": "EBL@Erick2026"
    },
]

existing_users = api("getAllUsers") or []
existing_usernames = [u['username'] for u in existing_users]

for u in usuarios:
    if u['username'] in existing_usernames:
        print(f"  ⏭️  {u['name']} já existe — pulando")
        continue
    result = api("createUser", {
        "username": u['username'],
        "name": u['name'],
        "email": u['email'],
        "role": u['role'],
        "password": u['password']
    })
    if result:
        print(f"  ✅ Criado: {u['name']} ({u['username']}) — Senha: {u['password']}")
    else:
        print(f"  ❌ Erro ao criar: {u['name']}")
    time.sleep(0.3)

# ============================================================
# 2. ADICIONAR TODOS OS USUÁRIOS AOS PROJETOS
# ============================================================
print("\n[2/4] ADICIONANDO USUÁRIOS AOS PROJETOS...")

all_users = api("getAllUsers") or []
all_projects = api("getAllProjects") or []

# Mapear usuários por username
user_map = {u['username']: u['id'] for u in all_users}
print(f"  Usuários encontrados: {list(user_map.keys())}")

for project in all_projects:
    pid = project['id']
    pname = project['name']
    members_added = 0
    for uname, uid in user_map.items():
        if uname == 'admin':
            continue
        result = api("addProjectUser", {"project_id": pid, "user_id": uid, "role": "project-member"})
        if result:
            members_added += 1
        time.sleep(0.1)
    print(f"  ✅ [{pname}] — {members_added} usuários adicionados")

# ============================================================
# 3. SANITIZAR COLUNAS — REMOVER PREFIXOS "EM" E PADRONIZAR
# ============================================================
print("\n[3/4] SANITIZANDO COLUNAS DE TODOS OS PROJETOS...")

# Mapeamento de sanitização
SANITIZE_MAP = {
    "Em Análise": "Análise",
    "Em Desenvolvimento": "Desenvolvimento",
    "Em Homologação": "Homologação",
    "Em Aprovação": "Aprovação",
    "Em Deploy": "Deploy",
    "Em Produção": "Produção",
    "Em Revisão": "Revisão",
    "Em Teste": "Teste",
    "Em Espera": "Aguardando",
    "Em Andamento": "Em Andamento",  # manter este
    "Concluído": "Concluído",
    "Cancelado": "Cancelado",
    "Backlog": "Backlog",
    "Refinamento": "Refinamento",
    "Priorizada": "Priorizada",
    "Estimativa": "Estimativa",
}

sanitized_count = 0
for project in all_projects:
    pid = project['id']
    pname = project['name']
    columns = api("getColumns", {"project_id": pid}) or []
    for col in columns:
        old_name = col['title']
        new_name = SANITIZE_MAP.get(old_name, old_name)
        # Remover qualquer prefixo "Em " que não esteja no mapa
        if new_name.startswith("Em ") and new_name not in ["Em Andamento"]:
            new_name = new_name[3:]
        if new_name != old_name:
            result = api("updateColumn", {
                "column_id": col['id'],
                "title": new_name,
                "task_limit": col.get('task_limit', 0),
                "description": col.get('description', '')
            })
            if result:
                print(f"  ✅ [{pname}] '{old_name}' → '{new_name}'")
                sanitized_count += 1
            time.sleep(0.1)

if sanitized_count == 0:
    print("  ✅ Todas as colunas já estão sanitizadas")
else:
    print(f"  ✅ {sanitized_count} colunas sanitizadas")

# ============================================================
# 4. CRIAR FILTROS PERSONALIZADOS EXECUTIVOS
# ============================================================
print("\n[4/4] CRIANDO FILTROS EXECUTIVOS NO PROJETO [SF]...")

SF_PROJECT_ID = 11

filters = [
    {
        "name": "🔴 Alta Prioridade",
        "filter": "priority:3 status:open",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "⚠️ Vencimento Próximo (7 dias)",
        "filter": "due:<=7 status:open",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "🚀 Em Desenvolvimento",
        "filter": "column:\"07. Desenvolvimento\" status:open",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "✅ Implementados",
        "filter": "status:closed",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "👤 Erick Almeida",
        "filter": "assignee:erick.almeida status:open",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "👤 Marcio Souza",
        "filter": "assignee:marcio.souza status:open",
        "project_id": SF_PROJECT_ID
    },
    {
        "name": "👤 Elder Rodrigues",
        "filter": "assignee:elder.rodrigues status:open",
        "project_id": SF_PROJECT_ID
    },
]

for f in filters:
    result = api("createFilter", {
        "project_id": f['project_id'],
        "name": f['name'],
        "filter": f['filter'],
        "user_id": 1,
        "is_shared": 1
    })
    if result:
        print(f"  ✅ Filtro criado: {f['name']}")
    else:
        print(f"  ⚠️  Filtro '{f['name']}' pode já existir")
    time.sleep(0.2)

# ============================================================
# RELATÓRIO FINAL
# ============================================================
print("\n" + "=" * 60)
print("  RELATÓRIO FINAL DE SANITIZAÇÃO")
print("=" * 60)

all_users_final = api("getAllUsers") or []
print(f"\n👥 USUÁRIOS CADASTRADOS ({len(all_users_final)}):")
print(f"  {'Username':<25} {'Nome':<25} {'Papel':<15}")
print(f"  {'-'*25} {'-'*25} {'-'*15}")
for u in all_users_final:
    role_label = {"app-admin": "Administrador", "app-manager": "Gerente", "app-user": "Usuário"}.get(u['role'], u['role'])
    print(f"  {u['username']:<25} {u['name']:<25} {role_label:<15}")

print(f"\n📋 PROJETOS E TAREFAS:")
for p in all_projects:
    open_t = api("getAllTasks", {"project_id": p['id'], "status_id": 1}) or []
    closed_t = api("getAllTasks", {"project_id": p['id'], "status_id": 0}) or []
    total = len(open_t) + len(closed_t)
    bar = "█" * min(total // 5, 20) if total > 0 else ""
    print(f"  [{p['id']:2d}] {p['name']:<40} | {bar} {total} tarefas")

print("\n✅ Sanitização completa!")
