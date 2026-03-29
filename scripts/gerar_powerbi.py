#!/usr/bin/env python3
"""
Gerador de Dados e Relatório Executivo para Power BI — Kanboard EBL
Extrai todos os dados do Kanboard e gera:
1. CSV pronto para importar no Power BI
2. Relatório HTML executivo completo
3. Arquivo de configuração Power BI (JSON)
"""
import requests, json, csv, os
from datetime import datetime, date
from collections import Counter, defaultdict

BASE = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php"
AUTH = ("admin", "Senha@2026")
OUTPUT_DIR = "/home/ubuntu/kanboard/powerbi"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def api(method, params={}):
    try:
        r = requests.post(BASE, auth=AUTH,
            json={"jsonrpc":"2.0","method":method,"id":1,"params":params},
            timeout=15)
        return r.json().get("result")
    except Exception as e:
        print(f"  ⚠️  Erro [{method}]: {e}")
        return None

print("Extraindo dados do Kanboard...")

# Buscar dados
projects = api("getAllProjects") or []
all_tasks = []
col_map = {}
sw_map = {}

for p in projects:
    pid = p['id']
    cols = api("getColumns", {"project_id": pid}) or []
    for c in cols:
        col_map[c['id']] = c['title']
    sws = api("getActiveSwimlanes", {"project_id": pid}) or []
    for s in sws:
        sw_map[s['id']] = s['name']
    open_t = api("getAllTasks", {"project_id": pid, "status_id": 1}) or []
    closed_t = api("getAllTasks", {"project_id": pid, "status_id": 0}) or []
    for t in open_t + closed_t:
        t['project_name'] = p['name']
    all_tasks.extend(open_t + closed_t)

print(f"  {len(all_tasks)} tarefas extraídas de {len(projects)} projetos")

# ============================================================
# 1. GERAR CSV PARA POWER BI
# ============================================================
csv_path = f"{OUTPUT_DIR}/kanboard_dados.csv"
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow([
        'ID', 'Titulo', 'Projeto', 'Fase', 'Responsavel_Raia',
        'Status', 'Prioridade', 'Prioridade_Texto', 'Cor',
        'Data_Criacao', 'Data_Modificacao', 'Data_Vencimento', 'Data_Conclusao',
        'Dias_Aberto', 'Em_Atraso', 'Descricao_Resumo',
        'ID_Cherwell', 'Tipo_Demanda', 'Area'
    ])
    for t in all_tasks:
        # Fase
        fase = col_map.get(t.get('column_id', 0), 'Desconhecida')
        # Swimlane / Responsável
        sw_name = sw_map.get(t.get('swimlane_id', 0), 'Geral')
        # Status
        status = 'Concluída' if t.get('is_active') == 0 else 'Aberta'
        # Prioridade
        prio = t.get('priority', 1)
        prio_txt = {3: 'Alta', 2: 'Média', 1: 'Baixa'}.get(prio, 'Baixa')
        # Datas
        def ts_to_date(ts):
            if ts and ts != 0:
                try: return datetime.fromtimestamp(int(ts)).strftime('%d/%m/%Y')
                except: return ''
            return ''
        dt_criacao = ts_to_date(t.get('date_creation'))
        dt_modif = ts_to_date(t.get('date_modification'))
        dt_venc = ts_to_date(t.get('date_due'))
        dt_conc = ts_to_date(t.get('date_completed'))
        # Dias aberto
        dias_aberto = ''
        if t.get('date_creation'):
            try:
                criado = datetime.fromtimestamp(int(t['date_creation']))
                fim = datetime.fromtimestamp(int(t['date_completed'])) if t.get('date_completed') else datetime.now()
                dias_aberto = str((fim - criado).days)
            except: pass
        # Em atraso
        em_atraso = 'Não'
        if t.get('date_due') and t.get('is_active') == 1:
            try:
                venc = datetime.fromtimestamp(int(t['date_due']))
                if venc.date() < date.today():
                    em_atraso = 'Sim'
            except: pass
        # Extrair ID Cherwell, tipo e área da descrição
        desc = t.get('description', '') or ''
        id_cherwell = ''
        tipo = ''
        area = ''
        for line in desc.split('\n'):
            if '**ID Cherwell:**' in line:
                id_cherwell = line.split('**ID Cherwell:**')[-1].strip().replace('#', '')
            elif '**📌 Tipo:**' in line:
                tipo = line.split('**📌 Tipo:**')[-1].strip()
            elif '**🏢 Área:**' in line:
                area = line.split('**🏢 Área:**')[-1].strip()
        # Resumo da descrição (primeiras 200 chars)
        desc_resumo = desc[:200].replace('\n', ' ').replace(';', ',') if desc else ''
        writer.writerow([
            t.get('id', ''),
            t.get('title', '').replace(';', ','),
            t.get('project_name', ''),
            fase,
            sw_name,
            status,
            prio,
            prio_txt,
            t.get('color_id', ''),
            dt_criacao,
            dt_modif,
            dt_venc,
            dt_conc,
            dias_aberto,
            em_atraso,
            desc_resumo,
            id_cherwell,
            tipo,
            area
        ])

print(f"  ✅ CSV gerado: {csv_path}")

# ============================================================
# 2. GERAR RELATÓRIO HTML EXECUTIVO
# ============================================================

# Calcular métricas
sf_tasks = [t for t in all_tasks if 'Salesforce' in t.get('project_name', '')]
total = len(sf_tasks)
abertas = sum(1 for t in sf_tasks if t.get('is_active') == 1)
concluidas = sum(1 for t in sf_tasks if t.get('is_active') == 0)
pct_concluido = round(concluidas / total * 100, 1) if total > 0 else 0

# Por fase
fase_count = Counter()
for t in sf_tasks:
    if t.get('is_active') == 1:
        fase = col_map.get(t.get('column_id', 0), 'Desconhecida')
        fase_count[fase] += 1

# Por responsável (swimlane)
resp_count = Counter()
for t in sf_tasks:
    if t.get('is_active') == 1:
        sw = sw_map.get(t.get('swimlane_id', 0), 'Geral')
        resp_count[sw] += 1

# Em atraso
atrasadas = 0
for t in sf_tasks:
    if t.get('date_due') and t.get('is_active') == 1:
        try:
            venc = datetime.fromtimestamp(int(t['date_due']))
            if venc.date() < date.today():
                atrasadas += 1
        except: pass

# Alta prioridade
alta_prio = sum(1 for t in sf_tasks if t.get('priority', 1) == 3 and t.get('is_active') == 1)

# Gerar HTML
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Executivo — Fast Track Salesforce | EBL</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; }}
  .header {{ background: linear-gradient(135deg, #1a1f2e 0%, #0d47a1 100%); padding: 30px 40px; border-bottom: 3px solid #2196F3; }}
  .header h1 {{ font-size: 28px; font-weight: 700; color: #fff; }}
  .header p {{ color: #90CAF9; margin-top: 5px; font-size: 14px; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 30px; }}
  .kpi-card {{ background: #1a1f2e; border-radius: 12px; padding: 20px; border-left: 4px solid; text-align: center; }}
  .kpi-card.blue {{ border-color: #2196F3; }}
  .kpi-card.green {{ border-color: #4CAF50; }}
  .kpi-card.orange {{ border-color: #FF9800; }}
  .kpi-card.red {{ border-color: #f44336; }}
  .kpi-card.purple {{ border-color: #9C27B0; }}
  .kpi-value {{ font-size: 42px; font-weight: 700; color: #fff; }}
  .kpi-label {{ font-size: 12px; color: #90A4AE; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px; }}
  .kpi-sub {{ font-size: 14px; color: #64B5F6; margin-top: 3px; }}
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
  .chart-card {{ background: #1a1f2e; border-radius: 12px; padding: 25px; }}
  .chart-card h3 {{ font-size: 16px; color: #90CAF9; margin-bottom: 20px; border-bottom: 1px solid #263238; padding-bottom: 10px; }}
  .bar-item {{ margin-bottom: 12px; }}
  .bar-label {{ font-size: 13px; color: #B0BEC5; margin-bottom: 4px; display: flex; justify-content: space-between; }}
  .bar-track {{ background: #263238; border-radius: 4px; height: 8px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .progress-ring {{ display: flex; align-items: center; justify-content: center; padding: 20px; }}
  .progress-circle {{ position: relative; width: 160px; height: 160px; }}
  .progress-circle svg {{ transform: rotate(-90deg); }}
  .progress-circle .bg {{ fill: none; stroke: #263238; stroke-width: 12; }}
  .progress-circle .fg {{ fill: none; stroke: #4CAF50; stroke-width: 12; stroke-linecap: round; stroke-dasharray: 440; }}
  .progress-text {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }}
  .progress-text .pct {{ font-size: 32px; font-weight: 700; color: #4CAF50; }}
  .progress-text .lbl {{ font-size: 11px; color: #90A4AE; }}
  .table-card {{ background: #1a1f2e; border-radius: 12px; padding: 25px; margin-bottom: 20px; }}
  .table-card h3 {{ font-size: 16px; color: #90CAF9; margin-bottom: 20px; border-bottom: 1px solid #263238; padding-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #0d47a1; color: #fff; padding: 10px 12px; text-align: left; font-weight: 600; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e2a3a; color: #CFD8DC; }}
  tr:hover td {{ background: #1e2a3a; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .badge-red {{ background: #b71c1c; color: #fff; }}
  .badge-orange {{ background: #e65100; color: #fff; }}
  .badge-green {{ background: #1b5e20; color: #fff; }}
  .badge-blue {{ background: #0d47a1; color: #fff; }}
  .badge-gray {{ background: #37474f; color: #fff; }}
  .footer {{ text-align: center; padding: 20px; color: #546E7A; font-size: 12px; border-top: 1px solid #1e2a3a; margin-top: 30px; }}
  .api-box {{ background: #0d1117; border: 1px solid #263238; border-radius: 8px; padding: 15px; font-family: monospace; font-size: 12px; color: #64B5F6; margin-top: 10px; word-break: break-all; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 Dashboard Executivo — Fast Track Salesforce</h1>
  <p>EBL Soluções Corporativas &nbsp;|&nbsp; Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} &nbsp;|&nbsp; Fonte: Kanboard API</p>
</div>
<div class="container">

  <!-- KPIs -->
  <div class="kpi-grid">
    <div class="kpi-card blue">
      <div class="kpi-value">{total}</div>
      <div class="kpi-label">Total de Demandas</div>
      <div class="kpi-sub">Projeto SF</div>
    </div>
    <div class="kpi-card green">
      <div class="kpi-value">{concluidas}</div>
      <div class="kpi-label">Implementadas</div>
      <div class="kpi-sub">{pct_concluido}% do total</div>
    </div>
    <div class="kpi-card orange">
      <div class="kpi-value">{abertas}</div>
      <div class="kpi-label">Em Andamento</div>
      <div class="kpi-sub">Abertas no pipeline</div>
    </div>
    <div class="kpi-card red">
      <div class="kpi-value">{atrasadas}</div>
      <div class="kpi-label">Em Atraso</div>
      <div class="kpi-sub">Prazo vencido</div>
    </div>
    <div class="kpi-card purple">
      <div class="kpi-value">{alta_prio}</div>
      <div class="kpi-label">Alta Prioridade</div>
      <div class="kpi-sub">Requer atenção</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-grid">
    <!-- Pipeline por Fase -->
    <div class="chart-card">
      <h3>📋 Pipeline por Fase</h3>
"""

max_fase = max(fase_count.values()) if fase_count else 1
fase_colors = {
    '01. Backlog': '#546E7A',
    '02. Refinamento': '#1565C0',
    '03. Priorizada': '#6A1B9A',
    '04. Análise': '#0277BD',
    '05. Estimativa': '#00838F',
    '06. Aprovação': '#F57F17',
    '07. Desenvolvimento': '#E65100',
    '08. Homologação': '#AD1457',
    '09. Deploy': '#558B2F',
    '10. Implementado': '#2E7D32',
    '11. Cancelado': '#37474F',
}

for fase, count in sorted(fase_count.items()):
    pct = round(count / max_fase * 100)
    color = fase_colors.get(fase, '#2196F3')
    html += f"""
      <div class="bar-item">
        <div class="bar-label"><span>{fase}</span><span><b>{count}</b></span></div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
      </div>"""

html += """
    </div>
    <!-- Por Responsável -->
    <div class="chart-card">
      <h3>👥 Distribuição por Responsável</h3>
"""

resp_colors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#f44336', '#00BCD4', '#FF5722']
max_resp = max(resp_count.values()) if resp_count else 1
for i, (resp, count) in enumerate(sorted(resp_count.items(), key=lambda x: -x[1])):
    pct = round(count / max_resp * 100)
    color = resp_colors[i % len(resp_colors)]
    pct_total = round(count / abertas * 100) if abertas > 0 else 0
    html += f"""
      <div class="bar-item">
        <div class="bar-label"><span>{resp}</span><span><b>{count}</b> ({pct_total}%)</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
      </div>"""

# Progress ring
stroke_val = round(pct_concluido / 100 * 440)
html += f"""
    </div>
  </div>

  <!-- Progress + Resumo -->
  <div class="charts-grid">
    <div class="chart-card" style="display:flex;align-items:center;justify-content:space-around;">
      <div>
        <h3>🎯 Taxa de Conclusão</h3>
        <div class="progress-ring">
          <div class="progress-circle">
            <svg width="160" height="160" viewBox="0 0 160 160">
              <circle class="bg" cx="80" cy="80" r="70"/>
              <circle class="fg" cx="80" cy="80" r="70" stroke-dashoffset="{440 - stroke_val}"/>
            </svg>
            <div class="progress-text">
              <div class="pct">{pct_concluido}%</div>
              <div class="lbl">Concluído</div>
            </div>
          </div>
        </div>
      </div>
      <div>
        <h3>📊 Resumo Executivo</h3>
        <br>
        <table style="width:auto">
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Total de Demandas</td><td><b style="color:#fff">{total}</b></td></tr>
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Implementadas</td><td><b style="color:#4CAF50">{concluidas}</b></td></tr>
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Em Andamento</td><td><b style="color:#2196F3">{abertas}</b></td></tr>
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Em Atraso</td><td><b style="color:#f44336">{atrasadas}</b></td></tr>
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Alta Prioridade</td><td><b style="color:#FF9800">{alta_prio}</b></td></tr>
          <tr><td style="color:#90A4AE;padding:6px 15px 6px 0">Responsáveis</td><td><b style="color:#9C27B0">{len(resp_count)}</b></td></tr>
        </table>
      </div>
    </div>

    <!-- API Integration Box -->
    <div class="chart-card">
      <h3>🔌 Integração Power BI — Endpoint API</h3>
      <p style="color:#90A4AE;font-size:13px;margin-bottom:10px">Use este endpoint no Power BI para atualização automática dos dados:</p>
      <div class="api-box">POST http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php<br>Auth: Basic admin:a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff<br>Method: getAllTasks | project_id: 11</div>
      <br>
      <p style="color:#90A4AE;font-size:13px;margin-bottom:5px">Arquivo CSV pronto para importação:</p>
      <div class="api-box">kanboard/powerbi/kanboard_dados.csv<br>{len(all_tasks)} registros | Separador: ponto e vírgula (;) | Encoding: UTF-8 BOM</div>
      <br>
      <p style="color:#64B5F6;font-size:12px">📌 O CSV contém: ID, Título, Projeto, Fase, Responsável, Status, Prioridade, Datas, Em Atraso, ID Cherwell, Tipo, Área</p>
    </div>
  </div>

  <!-- Tabela de Demandas Críticas -->
  <div class="table-card">
    <h3>🚨 Demandas que Requerem Atenção (Alta Prioridade / Em Atraso)</h3>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Título</th>
          <th>Fase</th>
          <th>Responsável</th>
          <th>Prazo</th>
          <th>Prioridade</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
"""

# Tarefas críticas: alta prioridade ou em atraso
criticas = []
for t in sf_tasks:
    if t.get('is_active') != 1:
        continue
    prio = t.get('priority', 1)
    em_atraso = False
    if t.get('date_due'):
        try:
            venc = datetime.fromtimestamp(int(t['date_due']))
            em_atraso = venc.date() < date.today()
        except: pass
    if prio == 3 or em_atraso:
        criticas.append((t, em_atraso))

criticas.sort(key=lambda x: (-x[0].get('priority', 1), x[0].get('date_due', 0) or 0))

for t, em_atraso in criticas[:20]:
    fase = col_map.get(t.get('column_id', 0), '—')
    resp = sw_map.get(t.get('swimlane_id', 0), '—')
    prio = t.get('priority', 1)
    prio_txt = {3: 'Alta', 2: 'Média', 1: 'Baixa'}.get(prio, 'Baixa')
    prio_badge = {3: 'badge-red', 2: 'badge-orange', 1: 'badge-gray'}.get(prio, 'badge-gray')
    prazo = ''
    if t.get('date_due'):
        try: prazo = datetime.fromtimestamp(int(t['date_due'])).strftime('%d/%m/%Y')
        except: pass
    atraso_badge = '<span class="badge badge-red">ATRASADO</span>' if em_atraso else '<span class="badge badge-green">No Prazo</span>'
    title = t.get('title', '')[:60]
    html += f"""
        <tr>
          <td>#{t.get('id')}</td>
          <td>{title}</td>
          <td>{fase}</td>
          <td>{resp}</td>
          <td>{prazo if prazo else '—'}</td>
          <td><span class="badge {prio_badge}">{prio_txt}</span></td>
          <td>{atraso_badge}</td>
        </tr>"""

if not criticas:
    html += '<tr><td colspan="7" style="text-align:center;color:#4CAF50">✅ Nenhuma demanda crítica no momento</td></tr>'

html += f"""
      </tbody>
    </table>
  </div>

  <!-- Tabela completa de todas as demandas -->
  <div class="table-card">
    <h3>📋 Todas as Demandas — [SF] Fast Track Salesforce ({total} registros)</h3>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Título</th>
          <th>Fase</th>
          <th>Responsável</th>
          <th>Prioridade</th>
          <th>Prazo</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
"""

for t in sorted(sf_tasks, key=lambda x: x.get('id', 0)):
    fase = col_map.get(t.get('column_id', 0), '—')
    resp = sw_map.get(t.get('swimlane_id', 0), '—')
    prio = t.get('priority', 1)
    prio_txt = {3: 'Alta', 2: 'Média', 1: 'Baixa'}.get(prio, 'Baixa')
    prio_badge = {3: 'badge-red', 2: 'badge-orange', 1: 'badge-gray'}.get(prio, 'badge-gray')
    prazo = ''
    if t.get('date_due'):
        try: prazo = datetime.fromtimestamp(int(t['date_due'])).strftime('%d/%m/%Y')
        except: pass
    status = 'Concluída' if t.get('is_active') == 0 else 'Aberta'
    status_badge = 'badge-green' if status == 'Concluída' else 'badge-blue'
    title = t.get('title', '')[:70]
    html += f"""
        <tr>
          <td>#{t.get('id')}</td>
          <td style="font-size:12px">{title}</td>
          <td>{fase}</td>
          <td>{resp}</td>
          <td><span class="badge {prio_badge}">{prio_txt}</span></td>
          <td>{prazo if prazo else '—'}</td>
          <td><span class="badge {status_badge}">{status}</span></td>
        </tr>"""

html += """
      </tbody>
    </table>
  </div>

</div>
<div class="footer">
  EBL Soluções Corporativas &nbsp;|&nbsp; Dashboard Executivo Kanboard &nbsp;|&nbsp; Dados em tempo real via API &nbsp;|&nbsp; kanboard.eblsolucoescorp.tec.br
</div>
</body>
</html>"""

html_path = f"{OUTPUT_DIR}/dashboard_executivo.html"
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"  ✅ Dashboard HTML gerado: {html_path}")

# ============================================================
# 3. GERAR ARQUIVO DE CONFIGURAÇÃO POWER BI (JSON)
# ============================================================
powerbi_config = {
    "kanboard_powerbi_config": {
        "versao": "1.0",
        "gerado_em": datetime.now().isoformat(),
        "conexao": {
            "url_api": "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php",
            "usuario": "admin",
            "token_api": "a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff",
            "autenticacao": "Basic (usuario:token_api em Base64)"
        },
        "projetos": {
            "sf_fast_track": {"id": 11, "nome": "[SF] Fast Track — Salesforce"},
            "comercial": {"id": 3, "nome": "[COM] Demandas Comercial"},
            "financeiro": {"id": 4, "nome": "[FIN] Demandas Financeiro"},
            "marketing": {"id": 2, "nome": "[MKT] Demandas de Marketing"},
            "operacoes": {"id": 12, "nome": "[OPS] Operações & Logística"},
            "projetos_internos": {"id": 5, "nome": "[PRJ] Projetos Internos"},
            "ti": {"id": 1, "nome": "[TI] Demandas de Tecnologia"}
        },
        "endpoints_powerbi": {
            "tarefas_abertas": {
                "method": "getAllTasks",
                "params": {"project_id": 11, "status_id": 1},
                "descricao": "Retorna todas as tarefas abertas do projeto SF"
            },
            "tarefas_fechadas": {
                "method": "getAllTasks",
                "params": {"project_id": 11, "status_id": 0},
                "descricao": "Retorna todas as tarefas concluídas"
            },
            "colunas": {
                "method": "getColumns",
                "params": {"project_id": 11},
                "descricao": "Retorna as fases/colunas do projeto"
            },
            "todos_projetos": {
                "method": "getAllProjects",
                "params": {},
                "descricao": "Retorna todos os projetos"
            }
        },
        "mapeamento_colunas": col_map,
        "mapeamento_swimlanes": sw_map,
        "metricas_atuais": {
            "total_demandas_sf": total,
            "abertas": abertas,
            "concluidas": concluidas,
            "pct_concluido": pct_concluido,
            "em_atraso": atrasadas,
            "alta_prioridade": alta_prio
        },
        "script_powerquery_m": """
let
    BaseUrl = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php",
    ApiToken = "a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff",
    Credentials = Binary.ToText(Text.ToBinary("admin:" & ApiToken), BinaryEncoding.Base64),
    GetTasks = (status_id as number) =>
        let
            Body = Json.FromValue([jsonrpc="2.0",method="getAllTasks",id=1,params=[project_id=11,status_id=status_id]]),
            Response = Web.Contents(BaseUrl,[Headers=[#"Content-Type"="application/json",#"Authorization"="Basic "&Credentials],Content=Body]),
            Result = Json.Document(Response)[result]
        in Result,
    Abertas = GetTasks(1),
    Fechadas = GetTasks(0),
    Todas = List.Combine({Abertas, Fechadas}),
    Tabela = Table.FromList(Todas, Splitter.SplitByNothing()),
    Expandida = Table.ExpandRecordColumn(Tabela, "Column1", {"id","title","column_id","swimlane_id","is_active","priority","color_id","date_due","date_creation","date_modification","date_completed","description"}),
    Tipada = Table.TransformColumnTypes(Expandida, {{"id",Int64.Type},{"column_id",Int64.Type},{"priority",Int64.Type},{"is_active",type logical}})
in Tipada
"""
    }
}

config_path = f"{OUTPUT_DIR}/powerbi_config.json"
with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(powerbi_config, f, ensure_ascii=False, indent=2)
print(f"  ✅ Config Power BI gerado: {config_path}")

print(f"\n{'='*60}")
print(f"  RELATÓRIO GERADO COM SUCESSO!")
print(f"{'='*60}")
print(f"  📊 Dashboard HTML: {html_path}")
print(f"  📄 CSV para Power BI: {csv_path}")
print(f"  ⚙️  Config JSON: {config_path}")
print(f"\n  MÉTRICAS ATUAIS [SF] Fast Track:")
print(f"  Total: {total} | Abertas: {abertas} | Concluídas: {concluidas} ({pct_concluido}%)")
print(f"  Em Atraso: {atrasadas} | Alta Prioridade: {alta_prio}")
