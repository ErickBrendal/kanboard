# Prompt para o Claude — Aplicar Tags Faltantes no Kanboard

> **Como usar:** Abra o Kanboard no navegador (`https://kanboard.eblsolucoescorp.tec.br`), ative a extensão do Claude e cole o conteúdo abaixo no chat.

---

```
Preciso que você verifique e complete as tags de TODAS as demandas do projeto "CRM Salesforce" no Kanboard que ainda não foram preenchidas ou foram preenchidas parcialmente.

## ACESSO
- URL: https://kanboard.eblsolucoescorp.tec.br
- Usuário: admin
- Senha: EBL@Kanboard2026
- Projeto: CRM Salesforce (project_id=1)
- API JSON-RPC: https://kanboard.eblsolucoescorp.tec.br/jsonrpc.php
- Auth API: usuário "jsonrpc", senha (token): ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317

## OBJETIVO
Para cada tarefa do projeto, verificar se ela já tem as tags corretas. Se não tiver (ou tiver incompleto), aplicar as tags da tabela de referência abaixo, usando o número do Cherwell como chave de correspondência.

O número do Cherwell de cada tarefa está no campo de descrição ou no título da tarefa no formato "#NNNNN" ou "Cherwell: NNNNN".

## COMO EXECUTAR (passo a passo via API)

### Passo 1 — Buscar todas as tarefas do projeto
```python
import requests

TOKEN = 'ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317'
URL   = 'https://kanboard.eblsolucoescorp.tec.br/jsonrpc.php'
AUTH  = ('jsonrpc', TOKEN)

def api(method, params=None, _id=[0]):
    _id[0] += 1
    r = requests.post(URL, json={'jsonrpc':'2.0','method':method,'id':_id[0],'params':params or {}}, auth=AUTH, timeout=15, verify=True)
    return r.json().get('result')

# Buscar tarefas abertas e fechadas
tarefas_abertas  = api('getAllTasks', {'project_id': 1, 'status_id': 1}) or []
tarefas_fechadas = api('getAllTasks', {'project_id': 1, 'status_id': 0}) or []
todas = tarefas_abertas + tarefas_fechadas
print(f"Total de tarefas: {len(todas)}")
```

### Passo 2 — Para cada tarefa, verificar as tags atuais
```python
# Verificar tags de uma tarefa
tags_atuais = api('getTaskTags', {'task_id': tarefa['id']})
# Retorna: {'tag_id': 'nome_tag', ...} ou {}
```

### Passo 3 — Identificar o Cherwell da tarefa
O número do Cherwell pode estar:
- No campo `reference` da tarefa
- No título: ex. "Cherwell 81643" ou "#81643"
- Na descrição da tarefa

### Passo 4 — Aplicar as tags corretas
```python
# Aplicar tags em uma tarefa (substitui todas as tags existentes)
api('updateTask', {
    'id': tarefa['id'],
    'tags': ['[TI] CRM Salesforce', '[SUB] Suporte Salesforce', '[NEG] Financeiro', '[RISCO] Baixo']
})
```

### Passo 5 — Lógica de verificação
- Se a tarefa já tem TODAS as tags corretas da tabela → PULAR (não modificar)
- Se a tarefa tem tags PARCIAIS ou NENHUMA → APLICAR todas as tags da tabela
- Se o Cherwell da tarefa NÃO está na tabela → PULAR e registrar no log

## TABELA DE REFERÊNCIA — Cherwell ID → Tags Corretas

| Cherwell | Projeto (resumido) | Tags a aplicar |
|---|---|---|
| 100006 | Cadastro de e-mails no depsnet | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Financeiro, [RISCO] Baixo |
| 100153 | Incluir no relatório do comissionado | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Bens de Consumo, [RISCO] Baixo |
| 100205 | Criação de uma visão para treinamentos | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Bens de Consumo, [RISCO] Baixo |
| 100512 | Implementar sistema de registro de garantia | [TI] Dados & Digital, [SUB] Site e Portal, [NEG] Automação, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 100971 | Inclusão de visão de Valor de Venda | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Bens de Consumo, [RISCO] Baixo, [REC] Interno |
| 100978 | Adequação no campo CNPJ - Reforma tributária | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Cadastros, [RISCO] Baixo |
| 100981 | Lists View e Aprovações em Massa | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Ar & Eletro, [RISCO] Baixo |
| 101061 | Automação Saldo/Cotas Salesforce / SAP | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Bens de Consumo, [RISCO] Baixo, [REC] Ambos, [ROI] Qualitativo |
| 101104 | DashBoard ENTREGAS (API Lincros) | [TI] Dados & Digital, [SUB] Dados e BI, [NEG] Logística, [RISCO] Médio, [REC] Interno, [ROI] N/A, [EVO] 51–75% |
| 101307 | Cadastrar preço por escritório de vendas | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Automação, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101308 | Envio de notificações aos clientes | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Logística, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101309 | ELNE: BLOQUEIO POR ESTADO | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Fiscal, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101310 | Criar relatórios de faturamento no Salesforce | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Financeiro, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101311 | Regras de Atribuição de leads Salesforce | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101312 | Integração via API do Salesforce e RD Station | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Marketing, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101313 | Preço por margem e tela de simulação | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101314 | Impedir que o mesmo sku seja inserido mais de uma vez | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] eCommerce, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101315 | Refatorar Integração Telecontrol X Salesforce | [TI] CRM Salesforce, [SUB] Integração, [NEG] Automação, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101316 | Integração de Imagens para Produtos no Salesforce | [TI] CRM Salesforce, [SUB] Integração, [NEG] eCommerce, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 101317 | Rastreabilidade de NFs Devolução e Garantia | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Logística, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 63681 | Melhoria Marketplace | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] TI, [RISCO] Baixo |
| 65244 | Aprovação Manual Garantia - Ar&eletro | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Ar & Eletro, [RISCO] Baixo |
| 66348 | Alteração de preços na inserção de produtos no pedido | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 66349 | Integração Salesforce para o Salesforce | [TI] CRM Salesforce, [SUB] Integração, [NEG] TI, [RISCO] Baixo |
| 67285 | ZVT2 - recebedor da mercadoria | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Logística, [RISCO] Baixo |
| 67286 | Habilitar marcar fase cancelado - BDVS | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 68285 | Inclusão de nova opção logistica - Pedidos Devolução | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Logística, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 69285 | Inclusão de visão de Valor de Venda - Garantia/Devolução | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Bens de Consumo, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 71285 | Cadastrar preço por escritório de vendas (Automação) | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Automação, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 75017 | Automatizar fluxo de Pedidos de Financiamento | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Financeiro, [RISCO] Baixo, [REC] Interno |
| 76285 | Integração via API do Salesforce e RD Station / Web to Lead | [TI] CRM Salesforce, [SUB] Integração, [NEG] Marketing, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| 77285 | Local de Expedição no Salesforce | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Logística, [RISCO] Baixo |
| 78285 | EDI para integração de pedidos - Cliente Leroy | [TI] CRM Salesforce, [SUB] Integração, [NEG] Comercial, [RISCO] Baixo |
| 78464 | Obrigação Fiscal - Declaração de PIs e Cofins | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Cadastros, [RISCO] Baixo |
| 79383 | Criação de Novo Tipo de Oportunidade | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Automação, [RISCO] Baixo |
| 80285 | Novo Calculo de Margem | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Financeiro, [RISCO] Baixo |
| 81285 | Melhoria no fluxo de cancelamentos - Bemol | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] eCommerce, [RISCO] Baixo |
| 81643 | Melhoria no fluxo de cancelamentos - Bemol e todos os pedidos | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] eCommerce, [RISCO] Baixo, [ROI] Qualitativo |
| 82285 | Formulário Quero Comprar Adição da BU de Automação SF | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Automação, [RISCO] Baixo |
| 83285 | Fluxo de consignação (Inclusão do processo de retorno simbólico) | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 85285 | Impedir que o mesmo sku seja inserido mais de uma vez no mesmo pedido | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] eCommerce, [RISCO] Baixo |
| 86285 | Preço por nível de Cliente | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 87285 | Consultar o último preço praticado na inserção de novos produtos | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 88285 | Aprovação Manual Garantia - Ar&eletro | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Ar & Eletro, [RISCO] Baixo |
| 89285 | Melhoria Marketplace | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] TI, [RISCO] Baixo |
| 90285 | Consultar o último preço praticado | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 91285 | Integração de Imagens para Produtos no Salesforce | [TI] CRM Salesforce, [SUB] Integração, [NEG] eCommerce, [RISCO] Baixo |
| 92285 | Rastreabilidade de NFs Devolução e Garantia - Lincros | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Logística, [RISCO] Baixo |
| 93285 | Preço por nível de Cliente | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 94285 | Refatorar Integração Telecontrol X Salesforce com Middleware | [TI] CRM Salesforce, [SUB] Integração, [NEG] Automação, [RISCO] Baixo |
| 95285 | Preço por margem e tela de simulação de preços | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 96285 | Integração via API do Salesforce e RD Station | [TI] CRM Salesforce, [SUB] Integração, [NEG] Marketing, [RISCO] Baixo |
| 97285 | Habilitar marcar fase cancelado - BDVS | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Comercial, [RISCO] Baixo |
| 98285 | ZVT2 - recebedor da mercadoria | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Logística, [RISCO] Baixo |
| 99285 | Local de Expedição no Salesforce | [TI] CRM Salesforce, [SUB] CRM Salesforce, [NEG] Logística, [RISCO] Baixo |
| 99383 | Criação de Novo Tipo de Oportunidade | [TI] CRM Salesforce, [SUB] Suporte Salesforce, [NEG] Automação, [RISCO] Baixo |
| D001 | Melhoria Marketplace (Dados) | [TI] Dados & Digital, [SUB] E-Commerce, [NEG] eCommerce, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| D002 | Automatizar fluxo de Pedidos (Dados) | [TI] Dados & Digital, [SUB] Dados e BI, [NEG] Financeiro, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| D003 | Integração Digital | [TI] Dados & Digital, [SUB] Integração, [NEG] TI, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| D004 | Site e Portal Apoio | [TI] Dados & Digital, [SUB] Site e Portal, [NEG] Marketing, [RISCO] Baixo, [REC] Interno, [ROI] N/A |
| D005 | Digital Geral | [TI] Dados & Digital, [SUB] Digital, [NEG] TI, [RISCO] Baixo, [REC] Interno, [ROI] N/A |

## LÓGICA DE CORRESPONDÊNCIA ENTRE TAREFA E CHERWELL

Como o Cherwell pode aparecer de formas diferentes no Kanboard, use esta ordem de busca:

1. Campo `reference` da tarefa (ex: "81643")
2. Título da tarefa contendo o número (ex: "#81643" ou "Cherwell 81643")
3. Descrição da tarefa contendo "Cherwell: 81643" ou "CHW-81643"
4. Correspondência pelo nome do projeto (últimos 40 caracteres do título)

Se não encontrar correspondência por nenhum método, PULE a tarefa e registre no log.

## REGRAS IMPORTANTES

1. **NÃO remova tags que já existem** se elas forem corretas — apenas ADICIONE as que estão faltando
2. **Se a tarefa já tem todas as tags** da tabela → PULE sem modificar
3. **Se a tarefa tem tags erradas** (ex: tag de outro projeto) → SUBSTITUA pelas corretas da tabela
4. **Processe em lotes de 10 tarefas** para evitar timeout
5. **Gere um relatório final** com:
   - Quantas tarefas tinham tags completas (não modificadas)
   - Quantas tarefas foram atualizadas
   - Quantas tarefas não foram encontradas na tabela
   - Lista das tarefas não encontradas

## EXEMPLO DE SCRIPT COMPLETO

```python
import requests, time

TOKEN = 'ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317'
URL   = 'https://kanboard.eblsolucoescorp.tec.br/jsonrpc.php'
AUTH  = ('jsonrpc', TOKEN)
_id   = [0]

def api(method, params=None):
    _id[0] += 1
    r = requests.post(URL, json={'jsonrpc':'2.0','method':method,'id':_id[0],'params':params or {}}, auth=AUTH, timeout=15, verify=True)
    return r.json().get('result')

# Tabela de referência (Cherwell -> tags)
TABELA = {
    '81643': ['[TI] CRM Salesforce', '[SUB] CRM Salesforce', '[NEG] eCommerce', '[RISCO] Baixo', '[ROI] Qualitativo'],
    '75017': ['[TI] CRM Salesforce', '[SUB] Suporte Salesforce', '[NEG] Financeiro', '[RISCO] Baixo', '[REC] Interno'],
    # ... (adicionar todas as linhas da tabela acima)
}

# Buscar todas as tarefas
tarefas = (api('getAllTasks', {'project_id': 1, 'status_id': 1}) or []) + \
          (api('getAllTasks', {'project_id': 1, 'status_id': 0}) or [])

atualizadas = 0
ja_completas = 0
nao_encontradas = []

for t in tarefas:
    # Tentar encontrar Cherwell
    cherwell = t.get('reference', '').strip()
    if not cherwell:
        # Buscar no título
        import re
        match = re.search(r'\b(\d{5,6})\b', t.get('title', ''))
        if match:
            cherwell = match.group(1)
    
    if cherwell not in TABELA:
        nao_encontradas.append({'id': t['id'], 'titulo': t['title'][:50], 'cherwell': cherwell})
        continue
    
    tags_corretas = TABELA[cherwell]
    tags_atuais = list((api('getTaskTags', {'task_id': t['id']}) or {}).values())
    
    # Verificar se já tem todas as tags corretas
    if all(tag in tags_atuais for tag in tags_corretas):
        ja_completas += 1
        continue
    
    # Aplicar tags corretas
    result = api('updateTask', {'id': t['id'], 'tags': tags_corretas})
    if result:
        atualizadas += 1
        print(f"✓ Tarefa #{t['id']} ({cherwell}): tags aplicadas")
    
    time.sleep(0.2)  # evitar sobrecarga

print(f"\n=== RELATÓRIO FINAL ===")
print(f"Tarefas já completas (não modificadas): {ja_completas}")
print(f"Tarefas atualizadas: {atualizadas}")
print(f"Tarefas não encontradas na tabela: {len(nao_encontradas)}")
if nao_encontradas:
    print("Não encontradas:")
    for t in nao_encontradas:
        print(f"  - #{t['id']} | Cherwell: {t['cherwell']} | {t['titulo']}")
```

Execute este script e me informe o relatório final.
```
