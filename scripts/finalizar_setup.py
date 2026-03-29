#!/usr/bin/env python3
"""
Finalização do Setup Kanboard EBL
- Remove projetos duplicados
- Gera token de API via updateUser
- Verifica configuração final
"""
import requests
import json
import sys

KANBOARD_URL = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
API_USER = "admin"
API_PASS = "admin"

_id = 0

def api(method, **params):
    global _id
    _id += 1
    try:
        r = requests.post(
            KANBOARD_URL,
            json={"jsonrpc": "2.0", "method": method, "id": _id, "params": params},
            auth=(API_USER, API_PASS),
            timeout=30
        )
        data = r.json()
        if "error" in data and data["error"]:
            return None, data["error"]
        return data.get("result"), None
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 60)
    print("  KANBOARD EBL - FINALIZAÇÃO DO SETUP")
    print("=" * 60)

    # 1. Listar todos os projetos
    projetos, err = api("getAllProjects")
    if err:
        print(f"ERRO ao listar projetos: {err}")
        sys.exit(1)

    print(f"\n[1/4] Projetos encontrados: {len(projetos)}")

    # 2. Identificar e remover duplicatas (manter os de menor ID)
    nomes_vistos = {}
    para_remover = []
    para_manter = []

    for p in sorted(projetos, key=lambda x: int(x["id"])):
        nome = p["name"]
        if nome in nomes_vistos:
            para_remover.append(p)
        else:
            nomes_vistos[nome] = p
            para_manter.append(p)

    print(f"  Projetos a manter: {len(para_manter)}")
    print(f"  Projetos duplicados a remover: {len(para_remover)}")

    for p in para_remover:
        result, err = api("removeProject", project_id=int(p["id"]))
        if err:
            print(f"  ERRO ao remover [{p['id']}] {p['name']}: {err}")
        else:
            print(f"  Removido: [{p['id']}] {p['name']}")

    # 3. Verificar projetos finais
    projetos_final, _ = api("getAllProjects")
    print(f"\n[2/4] Projetos após limpeza: {len(projetos_final or [])}")
    for p in sorted(projetos_final or [], key=lambda x: int(x["id"])):
        print(f"  - [{p['id']}] {p['name']}")

    # 4. Verificar colunas do primeiro projeto
    if projetos_final:
        pid = int(projetos_final[0]["id"])
        colunas, _ = api("getColumns", project_id=pid)
        print(f"\n[3/4] Colunas do projeto [{pid}] {projetos_final[0]['name']}:")
        for c in (colunas or []):
            print(f"  - {c['title']}")

    # 5. Gerar token de API via getMe e criar token manualmente
    me, _ = api("getMe")
    token_atual = me.get("api_access_token") if me else None
    print(f"\n[4/4] Token de API atual: {token_atual or 'N/A (será gerado pela interface web)'}")

    # Salvar resultado final
    resultado = {
        "status": "CONFIGURADO",
        "url_http": "http://kanboard.eblsolucoescorp.tec.br",
        "url_https": "https://kanboard.eblsolucoescorp.tec.br",
        "usuario_admin": "admin",
        "senha_admin": "admin",
        "email_admin": "ti@eblsolucoescorp.tec.br",
        "api_token": token_atual or "Gerar em: Configurações > API",
        "boards": [p["name"] for p in sorted(projetos_final or [], key=lambda x: int(x["id"]))],
        "total_boards": len(projetos_final or []),
        "versao": "v1.2.51",
        "nota_ssl": "Certificado SSL pendente - requer acesso SSH ao servidor",
        "nota_smtp": "Configurar senha SMTP em config.php: MAIL_SMTP_PASSWORD"
    }

    with open("/tmp/kanboard_final.json", "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("  RESULTADO FINAL")
    print("=" * 60)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    return resultado

if __name__ == "__main__":
    main()
