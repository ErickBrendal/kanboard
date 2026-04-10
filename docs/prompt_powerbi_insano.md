# PROMPT DEFINITIVO — Power BI Dashboard EBL (Nível Insano)

> **Como usar:** Abra o Power BI Service em https://app.powerbi.com, acesse o relatório "EBL — Portfólio TI | Dashboard Executivo", ative a extensão do Claude e cole este prompt completo. Execute os blocos **em ordem**, confirmando cada etapa antes de avançar.

---

## CONTEXTO COMPLETO PARA O CLAUDE

Você é um especialista em Power BI e vai transformar um relatório básico em um dashboard executivo de nível enterprise, idêntico visualmente ao site https://eblsolucoescorporativas.com/.

### Credenciais e Acessos

| Item | Valor |
|---|---|
| Power BI URL | https://app.powerbi.com |
| Relatório | EBL — Portfólio TI \| Dashboard Executivo |
| Report ID | 8d4a1f93-7c5f-4197-8cf5-57c6aa08d154 |
| Dataset ID | 39d50fe5-cde9-4244-b5e5-422a73e8e142 |
| Workspace | My workspace |
| Kanboard API | http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php |
| Kanboard Token | ea99d4c7d96dbad1b1a1defd79f92286884e1902015ff96731ce624e6317 |
| Kanboard Projeto | CRM Salesforce (project_id=1) |

### Identidade Visual EBL (OBRIGATÓRIO aplicar em TUDO)

```json
{
  "background_principal": "#0d1117",
  "background_card": "#161b22",
  "background_card_hover": "#1c2128",
  "borda_card": "#30363d",
  "texto_principal": "#e6edf3",
  "texto_secundario": "#8b949e",
  "ciano_primario": "#00d4ff",
  "verde_sucesso": "#10b981",
  "amarelo_atencao": "#f59e0b",
  "vermelho_critico": "#ef4444",
  "roxo_especial": "#8b5cf6",
  "laranja_roi": "#f97316",
  "fonte": "Segoe UI, sans-serif",
  "borda_radius": "8px"
}
```

### Estrutura do Dataset (tabelas existentes no Power BI)

**Tabela: Demandas** — 28 colunas principais:
- `id`, `titulo`, `fase`, `area`, `tipo`, `status`, `prazo_status`
- `responsavel`, `prioridade`, `data_criacao`, `data_conclusao`
- `descricao`, `reference` (Cherwell ID)
- `custo_planejado`, `custo_realizado`, `valor_roi`, `roi_aprovado`
- `evolucao_planejado_pct`, `evolucao_realizado_pct`, `desvio_pct`
- `data_inicio_planejado`, `data_fim_planejado`, `data_golive_estimada`
- `subcategoria`, `area_negocio`, `classificacao_risco`, `recurso_tipo`
- `tags` (contém prefixos: [TI], [SUB], [NEG], [RISCO], [REC], [ROI], [EVO])

**Tabela: KPIs** — campos: `kpi_nome`, `kpi_valor`, `kpi_categoria`

**Tabela: Fases** — campos: `fase_nome`, `fase_ordem`, `fase_count`

**Tabela: Responsaveis** — campos: `responsavel_nome`, `total_demandas`, `abertas`, `concluidas`

### Mapeamento de Fases (sequência correta)

| Ordem | Fase no Dataset |
|---|---|
| 01 | 01. Ideação / POC |
| 02 | 02. Novo |
| 03 | 03. Backlog |
| 04 | 04. Análise TI |
| 05 | 05. Planejamento |
| 06 | 06. Pendente Aprovação |
| 07 | 07. Em Desenvolvimento |
| 08 | 08. Testes |
| 09 | 09. Hypercare |
| 10 | 10. Concluído |
| 11 | 11. On Hold |
| 12 | 12. Cancelado |

---

## PROBLEMAS IDENTIFICADOS NO RELATÓRIO ATUAL

1. **Fundo branco** — o relatório usa o tema padrão claro do Power BI, precisa ser dark `#0d1117`
2. **Títulos genéricos** — as demandas aparecem como "Demanda #1", "Demanda #2" em vez dos títulos reais
3. **Sem medidas DAX** — KPIs são contagens brutas sem cálculos de % conclusão, desvio, ROI
4. **Gráficos básicos** — apenas barras simples sem cores condicionais, sem formatação EBL
5. **Dados desatualizados** — última atualização em 29/03/2026, precisa de atualização automática
6. **Página Visão Geral incompleta** — apenas 1 card e 2 gráficos; precisa de 8 cards KPI + 4 gráficos
7. **Página Pipeline vazia** — sem funil de fases, sem indicadores de atraso
8. **Página Equipe vazia** — sem distribuição por responsável
9. **Página Financeiro vazia** — sem KPIs de custo, ROI, desvio
10. **Títulos das colunas em inglês** — `titulo`, `fase`, `area` devem ser "Título", "Fase", "Área"

---

## BLOCO 1 — ATUALIZAR DADOS DO KANBOARD (Execute primeiro)

```
Acesse o Power BI Service. No dataset "EBL — Portfólio TI | Dashboard Executivo" (ID: 39d50fe5-cde9-4244-b5e5-422a73e8e142), execute uma atualização manual dos dados agora. 

Se não conseguir atualizar via interface, use a REST API do Power BI:
- Endpoint: POST https://api.powerbi.com/v1.0/myorg/datasets/39d50fe5-cde9-4244-b5e5-422a73e8e142/refreshes
- Autenticação: Bearer token (obter via MSAL com client_id=1950a258-227b-4e31-a9cf-717495945fc2, tenant=208364c6-eee7-4324-ac4a-d45fe452a1bd, usuário admebl@eblsolucoescorporativas.com, senha Senha@2026)

Confirme quando a atualização estiver concluída.
```

---

## BLOCO 2 — CRIAR MEDIDAS DAX (Cole no editor DAX do Power BI Desktop ou via API)

```
No relatório Power BI, entre no modo de edição (botão "Editar" no canto superior direito). 
Crie as seguintes medidas DAX na tabela "Demandas":

// ===== MEDIDAS PRINCIPAIS =====

Total Demandas = COUNTROWS(Demandas)

Demandas Concluídas = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "10. Concluído")

% Conclusão = DIVIDE([Demandas Concluídas], [Total Demandas], 0) * 100

Em Andamento = CALCULATE(COUNTROWS(Demandas), 
    Demandas[fase] IN {"07. Em Desenvolvimento", "08. Testes", "09. Hypercare"})

No Backlog = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "03. Backlog")

Alta Prioridade = CALCULATE(COUNTROWS(Demandas), Demandas[prioridade] = "0")

Bloqueadas = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "11. On Hold")

Canceladas = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "12. Cancelado")

Pendente Aprovação = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "06. Pendente Aprovação")

// ===== MEDIDAS FINANCEIRAS =====

Custo Total Planejado = SUM(Demandas[custo_planejado])

Custo Total Realizado = SUM(Demandas[custo_realizado])

Desvio Custo % = DIVIDE([Custo Total Realizado] - [Custo Total Planejado], [Custo Total Planejado], 0) * 100

ROI Total = SUM(Demandas[valor_roi])

Projetos com ROI = CALCULATE(COUNTROWS(Demandas), Demandas[roi_aprovado] = "Sim")

// ===== MEDIDAS DE EVOLUÇÃO =====

Evolução Média Planejada = AVERAGE(Demandas[evolucao_planejado_pct])

Evolução Média Realizada = AVERAGE(Demandas[evolucao_realizado_pct])

Desvio Médio % = AVERAGE(Demandas[desvio_pct])

Confirme quando todas as 17 medidas forem criadas com sucesso.
```

---

## BLOCO 3 — APLICAR TEMA DARK EBL

```
No Power BI (modo edição), vá em: Exibição > Temas > Personalizar tema atual

Configure EXATAMENTE assim:

CORES PRINCIPAIS:
- Cor 1 (Primária): #00d4ff
- Cor 2: #10b981
- Cor 3: #f59e0b
- Cor 4: #ef4444
- Cor 5: #8b5cf6
- Cor 6: #f97316
- Cor 7: #06b6d4
- Cor 8: #84cc16

PLANO DE FUNDO:
- Fundo da tela: #0d1117
- Fundo do visual: #161b22
- Fundo do painel de filtros: #161b22

TEXTO:
- Cor do texto: #e6edf3
- Cor do título: #00d4ff
- Família da fonte: Segoe UI
- Tamanho do texto: 12

BORDAS:
- Cor da borda: #30363d
- Espessura da borda: 1px
- Raio da borda: 8px

Salve o tema como "EBL-Dark-Theme" e aplique em todo o relatório.

Se preferir importar via JSON, use este arquivo:
{
  "name": "EBL Dark Theme",
  "dataColors": ["#00d4ff","#10b981","#f59e0b","#ef4444","#8b5cf6","#f97316","#06b6d4","#84cc16"],
  "background": "#0d1117",
  "foreground": "#e6edf3",
  "tableAccent": "#00d4ff",
  "visualStyles": {
    "*": {
      "*": {
        "background": [{"color": {"solid": {"color": "#161b22"}}}],
        "border": [{"show": true, "color": {"solid": {"color": "#30363d"}}}],
        "title": [{"fontColor": {"solid": {"color": "#00d4ff"}}, "background": {"solid": {"color": "#0d1117"}}}]
      }
    }
  }
}

Confirme quando o tema dark estiver aplicado em todas as páginas.
```

---

## BLOCO 4 — RECONSTRUIR PÁGINA "VISÃO GERAL"

```
Acesse a página "Visão Geral" do relatório (modo edição).
Delete todos os visuais existentes e reconstrua do zero:

LAYOUT DA PÁGINA (1280x720px, fundo #0d1117):

=== CABEÇALHO (altura: 60px, largura total) ===
- Caixa de texto: "EBL — Portfólio TI | Dashboard Executivo"
  - Fonte: Segoe UI Bold, 20px, cor #00d4ff
  - Posição: x=20, y=10
- Caixa de texto: "EBL Soluções Corporativas"
  - Fonte: Segoe UI, 12px, cor #8b949e
  - Posição: x=20, y=35
- Linha separadora: cor #30363d, espessura 1px, y=60

=== LINHA 1 — 8 CARDS KPI (y=80, altura=100px) ===
Crie 8 cartões de KPI com largura=145px, espaçamento=10px:

Card 1 — "TOTAL DE DEMANDAS"
  - Medida: [Total Demandas]
  - Ícone: 📊
  - Cor do valor: #00d4ff
  - Borda esquerda: 3px solid #00d4ff
  - Fundo: #161b22

Card 2 — "IMPLEMENTADAS"
  - Medida: [Demandas Concluídas]
  - Subtítulo: [% Conclusão] & "% de conclusão"
  - Ícone: ✅
  - Cor do valor: #10b981
  - Borda esquerda: 3px solid #10b981
  - Fundo: #161b22

Card 3 — "EM ANDAMENTO"
  - Medida: [Em Andamento]
  - Subtítulo: "Dev + Testes + Hypercare"
  - Ícone: ⚡
  - Cor do valor: #f59e0b
  - Borda esquerda: 3px solid #f59e0b
  - Fundo: #161b22

Card 4 — "ALTA PRIORIDADE"
  - Medida: [Alta Prioridade]
  - Subtítulo: "Atenção imediata"
  - Ícone: 🔴
  - Cor do valor: #ef4444
  - Borda esquerda: 3px solid #ef4444
  - Fundo: #161b22

Card 5 — "NO BACKLOG"
  - Medida: [No Backlog]
  - Subtítulo: "% aguardando"
  - Ícone: 📦
  - Cor do valor: #8b5cf6
  - Borda esquerda: 3px solid #8b5cf6
  - Fundo: #161b22

Card 6 — "BLOQUEADAS"
  - Medida: [Bloqueadas]
  - Subtítulo: "On Hold / Impedimento"
  - Ícone: 🚧
  - Cor do valor: #f97316
  - Borda esquerda: 3px solid #f97316
  - Fundo: #161b22

Card 7 — "CANCELADAS"
  - Medida: [Canceladas]
  - Subtítulo: "Fora do escopo"
  - Ícone: ❌
  - Cor do valor: #ef4444
  - Borda esquerda: 3px solid #ef4444
  - Fundo: #161b22

Card 8 — "PENDENTE APROVAÇÃO"
  - Medida: [Pendente Aprovação]
  - Subtítulo: "Aguardando aprovação"
  - Ícone: ⏳
  - Cor do valor: #f59e0b
  - Borda esquerda: 3px solid #f59e0b
  - Fundo: #161b22

=== LINHA 2 — 2 GRÁFICOS PRINCIPAIS (y=200, altura=220px) ===

Gráfico 1 — "Distribuição por Fase" (largura=600px)
  - Tipo: Gráfico de barras horizontais
  - Eixo Y: campo "fase" (ordenado por fase_ordem ASC)
  - Eixo X: medida [Total Demandas] ou COUNT(id)
  - Cores das barras por fase:
    * 03. Backlog: #8b5cf6
    * 07. Em Desenvolvimento: #f59e0b
    * 10. Concluído: #10b981
    * 11. On Hold: #f97316
    * 12. Cancelado: #ef4444
    * demais: #00d4ff
  - Fundo: #161b22, borda: #30363d
  - Título: "Distribuição por Fase", cor #00d4ff, fonte 14px Bold
  - Rótulos de dados: ativados, cor #e6edf3

Gráfico 2 — "Por Prioridade" (largura=350px, x=660)
  - Tipo: Gráfico de rosca (Donut)
  - Legenda: campo "prioridade" (0=Normal, 1=Alta, 2=Urgente)
  - Valores: COUNT(id)
  - Cores: Normal=#00d4ff, Alta=#f59e0b, Urgente=#ef4444
  - Fundo: #161b22, borda: #30363d
  - Título: "Por Prioridade", cor #00d4ff

=== LINHA 3 — STATUS GERAL (y=440, altura=100px) ===
Crie uma tabela de status com 6 colunas:

| Abertas | Em Progresso | Implementadas | Bloqueadas | Canceladas | % Conclusão |
|---------|-------------|---------------|------------|------------|-------------|
| [valor] | [valor]     | [valor]       | [valor]    | [valor]    | [valor]%    |

- Cada célula: fundo #161b22, borda #30363d, texto centralizado
- Cores dos valores: Abertas=#00d4ff, Em Progresso=#f59e0b, Implementadas=#10b981, Bloqueadas=#f97316, Canceladas=#ef4444, % Conclusão=#10b981

Confirme quando a página Visão Geral estiver completa.
```

---

## BLOCO 5 — RECONSTRUIR PÁGINA "PIPELINE"

```
Acesse a página "Pipeline" (modo edição). Delete os visuais existentes.

=== CABEÇALHO ===
- Título: "🔄 Pipeline — Fluxo de Demandas"
- Subtítulo: "Quantidade de demandas por etapa do processo"
- Mesma formatação do cabeçalho da Visão Geral

=== VISUAL 1 — FUNIL DO PIPELINE (largura=600px, altura=350px) ===
- Tipo: Gráfico de funil (Funnel chart)
- Categoria: campo "fase" (ordenado por fase_ordem)
- Valores: COUNT(id)
- Cores: gradiente de #00d4ff (topo) até #10b981 (base)
- Fundo: #161b22
- Título: "Fluxo do Pipeline"
- Rótulos: mostrar valor e % do total

=== VISUAL 2 — DISTRIBUIÇÃO DETALHADA (largura=600px, altura=280px, x=660) ===
- Tipo: Gráfico de barras verticais agrupadas
- Eixo X: campo "fase" (ordenado por fase_ordem)
- Valores: COUNT(id) — barra azul #00d4ff
- Linha secundária: [% Conclusão] acumulado — linha verde #10b981
- Fundo: #161b22
- Título: "Distribuição Detalhada por Fase"

=== VISUAL 3 — TABELA DE DEMANDAS ATRASADAS (largura=1200px, altura=200px, y=400) ===
- Tipo: Tabela
- Colunas: id, titulo, fase, responsavel, data_golive_estimada, prazo_status
- Filtro: prazo_status = "atrasado" OU "vencido"
- Formatação condicional na coluna "prazo_status": vermelho #ef4444
- Título: "⚠️ Demandas em Atraso"
- Fundo: #161b22, cabeçalho: #0d1117, texto cabeçalho: #00d4ff

Confirme quando a página Pipeline estiver completa.
```

---

## BLOCO 6 — RECONSTRUIR PÁGINA "PROJETOS"

```
Acesse a página "Projetos" (modo edição). Delete os visuais existentes.

=== FILTROS NO TOPO (y=70, altura=50px) ===
Crie 4 segmentações de dados em linha:
1. Segmentação "Fase": campo fase, estilo lista suspensa, largura=200px
2. Segmentação "Área": campo area, estilo lista suspensa, largura=200px
3. Segmentação "Responsável": campo responsavel, estilo lista suspensa, largura=200px
4. Segmentação "Prioridade": campo prioridade, estilo lista suspensa, largura=200px

=== TABELA PRINCIPAL (y=130, largura=1200px, altura=500px) ===
- Tipo: Tabela com formatação condicional
- Colunas e formatação:
  * "ID" (id): largura=40px, alinhado à direita
  * "Título" (titulo): largura=300px, texto azul #00d4ff ao passar mouse
  * "Fase" (fase): largura=160px, com badge colorido por fase
  * "Área" (area): largura=120px
  * "Tipo" (tipo): largura=130px
  * "Responsável" (responsavel): largura=130px
  * "Prioridade" (prioridade): largura=80px, formatação condicional:
    - 0 = "Normal" cor #8b949e
    - 1 = "Alta" cor #f59e0b com fundo #2d1f00
    - 2 = "Urgente" cor #ef4444 com fundo #2d0000
  * "Status" (status): largura=80px, verde se "Fechada", azul se "Aberta"
  * "Prazo" (prazo_status): largura=100px, vermelho se "atrasado"
  * "Evolução %" (evolucao_realizado_pct): largura=100px, barra de progresso verde

- Cabeçalho: fundo #0d1117, texto #00d4ff, negrito
- Linhas alternadas: #161b22 e #1c2128
- Borda: #30363d
- Paginação: 20 linhas por página

Confirme quando a página Projetos estiver completa.
```

---

## BLOCO 7 — RECONSTRUIR PÁGINA "EQUIPE"

```
Acesse a página "Equipe" (modo edição). Delete os visuais existentes.

=== VISUAL 1 — CARGA POR RESPONSÁVEL (largura=580px, altura=300px) ===
- Tipo: Gráfico de barras horizontais
- Eixo Y: campo "responsavel"
- Eixo X: COUNT(id) — total de demandas
- Série adicional: [Demandas Concluídas] por responsável — cor #10b981
- Série principal: demandas abertas — cor #00d4ff
- Título: "👥 Carga por Responsável"
- Fundo: #161b22

=== VISUAL 2 — DISTRIBUIÇÃO POR FASE E RESPONSÁVEL (largura=580px, altura=300px, x=620) ===
- Tipo: Gráfico de barras empilhadas 100%
- Eixo X: campo "responsavel"
- Legenda: campo "fase"
- Valores: COUNT(id)
- Cores: usar paleta EBL (ciano, verde, amarelo, vermelho, roxo...)
- Título: "Distribuição por Fase e Responsável"
- Fundo: #161b22

=== VISUAL 3 — TABELA RESUMO DA EQUIPE (largura=1200px, altura=200px, y=330) ===
- Tipo: Tabela
- Colunas: responsavel, total demandas, abertas, em andamento, concluídas, % conclusão
- Formatação: igual ao padrão EBL dark
- Título: "Resumo da Equipe"

Confirme quando a página Equipe estiver completa.
```

---

## BLOCO 8 — RECONSTRUIR PÁGINA "FINANCEIRO"

```
Acesse a página "Financeiro" (modo edição). Delete os visuais existentes.

=== LINHA 1 — 4 CARDS FINANCEIROS (y=80, altura=100px) ===

Card 1 — "CUSTO PLANEJADO TOTAL"
  - Medida: [Custo Total Planejado]
  - Formato: R$ #.##0,00
  - Cor: #00d4ff, borda esquerda #00d4ff

Card 2 — "CUSTO REALIZADO TOTAL"
  - Medida: [Custo Total Realizado]
  - Formato: R$ #.##0,00
  - Cor: #f59e0b, borda esquerda #f59e0b

Card 3 — "DESVIO DE CUSTO"
  - Medida: [Desvio Custo %]
  - Formato: +0,0%;-0,0%
  - Cor condicional: verde se ≤0%, vermelho se >0%
  - Borda esquerda: condicional verde/vermelho

Card 4 — "ROI TOTAL APROVADO"
  - Medida: [ROI Total]
  - Formato: R$ #.##0,00
  - Cor: #10b981, borda esquerda #10b981

=== VISUAL 1 — CUSTO PLANEJADO VS REALIZADO (largura=580px, altura=280px, y=200) ===
- Tipo: Gráfico de barras agrupadas
- Eixo X: campo "fase"
- Série 1: SUM(custo_planejado) — cor #00d4ff
- Série 2: SUM(custo_realizado) — cor #f59e0b
- Título: "Custo Planejado vs Realizado por Fase"
- Fundo: #161b22

=== VISUAL 2 — EVOLUÇÃO DO ROI (largura=580px, altura=280px, x=620, y=200) ===
- Tipo: Gráfico de dispersão
- Eixo X: custo_planejado
- Eixo Y: valor_roi
- Tamanho da bolha: evolucao_realizado_pct
- Detalhes: titulo
- Cor: #10b981
- Título: "ROI vs Custo por Demanda"
- Fundo: #161b22

=== VISUAL 3 — TABELA FINANCEIRA (largura=1200px, altura=200px, y=500) ===
- Colunas: titulo, fase, custo_planejado, custo_realizado, desvio_pct, roi_aprovado, valor_roi
- Formatação condicional em desvio_pct: verde se ≤0, vermelho se >0
- Título: "Detalhamento Financeiro por Demanda"

Confirme quando a página Financeiro estiver completa.
```

---

## BLOCO 9 — RECONSTRUIR PÁGINA "DEMANDAS"

```
Acesse a página "Demandas" (modo edição). Delete os visuais existentes.

=== BARRA DE BUSCA (y=70, largura=400px) ===
- Adicione uma segmentação de dados do tipo "Pesquisa" no campo "titulo"
- Placeholder: "🔍 Buscar demanda..."
- Fundo: #161b22, borda: #30363d, texto: #e6edf3

=== FILTROS RÁPIDOS (y=70, x=430, largura=750px) ===
- 3 segmentações em linha: Fase, Área Negócio, Classificação Risco
- Estilo: botões (não lista), fundo ativo: #00d4ff, texto ativo: #0d1117

=== TABELA MESTRE (y=130, largura=1200px, altura=520px) ===
Colunas (nesta ordem):
1. "Nº" (id): 40px, cinza #8b949e
2. "Título" (titulo): 280px, cor #e6edf3, negrito
3. "Cherwell" (reference): 80px, cor #8b949e
4. "Fase" (fase): 150px, badge colorido:
   - 10. Concluído: fundo #0d2818, texto #10b981
   - 07. Em Desenvolvimento: fundo #2d1f00, texto #f59e0b
   - 11. On Hold: fundo #2d1500, texto #f97316
   - 12. Cancelado: fundo #2d0000, texto #ef4444
   - 03. Backlog: fundo #1a1040, texto #8b5cf6
   - demais: fundo #0d1f2d, texto #00d4ff
5. "Área TI" (tipo): 120px
6. "Área Negócio" (area_negocio): 120px
7. "Responsável" (responsavel): 120px
8. "Risco" (classificacao_risco): 80px, badge:
   - Baixo: verde #10b981
   - Médio: amarelo #f59e0b
   - Alto: vermelho #ef4444
9. "Evolução" (evolucao_realizado_pct): 90px, barra de progresso:
   - 0-30%: vermelho #ef4444
   - 31-70%: amarelo #f59e0b
   - 71-100%: verde #10b981
10. "GoLive" (data_golive_estimada): 90px, formato dd/mm/aaaa
11. "Prazo" (prazo_status): 80px, formatação condicional

- Cabeçalho: fundo #0d1117, texto #00d4ff, negrito, 12px
- Linhas alternadas: #161b22 / #1c2128
- Borda: #30363d
- Paginação: 25 linhas por página
- Título: "📋 Todas as Demandas"

Confirme quando a página Demandas estiver completa.
```

---

## BLOCO 10 — CONFIGURAR ATUALIZAÇÃO AUTOMÁTICA

```
Configure a atualização automática do dataset para sincronizar com o Kanboard:

PASSO 1 — Configurar gateway (se necessário):
- Acesse: Configurações > Gerenciar conexões e gateways
- Verifique se o dataset "EBL — Portfólio TI" está conectado

PASSO 2 — Agendar atualização:
- Acesse: My workspace > Dataset "EBL — Portfólio TI | Dashboard Executivo"
- Clique nos 3 pontos > Configurações > Atualização agendada
- Ative: "Manter os dados atualizados"
- Frequência: Diária
- Fuso horário: (UTC-03:00) Brasília
- Horários: 07:00, 09:00, 12:00, 15:00, 18:00
- Email de notificação: admebl@eblsolucoescorporativas.com

PASSO 3 — Configurar atualização via script Python (para atualização em tempo real):
O script sync_powerbi_v4.py já está configurado no servidor Oracle Cloud.
Para executar automaticamente a cada hora, adicione ao crontab do servidor:
0 * * * * cd /home/ubuntu/kanboard && python3 scripts/sync_powerbi_v4.py >> /var/log/sync_powerbi.log 2>&1

Confirme quando a atualização automática estiver configurada.
```

---

## BLOCO 11 — CONFIGURAR EMBED NO SITE EBL

```
Para integrar o Power BI no site https://eblsolucoescorporativas.com/:

PASSO 1 — Habilitar "Publicar na Web" no tenant:
- Acesse: https://admin.powerbi.com
- Vá em: Configurações do Tenant > Configurações de exportação e compartilhamento
- Habilite: "Publicar na Web"
- Aplique para: Toda a organização

PASSO 2 — Gerar código de incorporação:
- Abra o relatório "EBL — Portfólio TI | Dashboard Executivo"
- Clique em: Arquivo > Incorporar relatório > Publicar na Web
- Copie o código iframe gerado

PASSO 3 — Atualizar o site EBL:
O site está hospedado no servidor Oracle Cloud em /home/ubuntu/ebl-dashboard/
O arquivo a editar é: src/components/PowerBIEmbed.tsx (ou similar)

Substitua o iframe placeholder pelo código real:
<iframe
  title="EBL — Portfólio TI | Dashboard Executivo"
  src="[URL_GERADA_NO_PASSO_2]"
  frameborder="0"
  allowFullScreen="true"
  style={{
    width: '100%',
    height: '600px',
    border: '1px solid #30363d',
    borderRadius: '8px',
    background: '#0d1117'
  }}
/>

Se "Publicar na Web" não estiver disponível, use embed com autenticação:
- Client ID: 1950a258-227b-4e31-a9cf-717495945fc2
- Tenant ID: 208364c6-eee7-4324-ac4a-d45fe452a1bd
- Report ID: 8d4a1f93-7c5f-4197-8cf5-57c6aa08d154
- Workspace ID: me (My workspace)

Confirme quando o embed estiver funcionando no site.
```

---

## BLOCO 12 — VALIDAÇÃO FINAL

```
Execute a validação completa do dashboard:

1. Verifique se TODAS as 6 páginas estão com fundo dark #0d1117
2. Confirme que os 8 cards KPI da Visão Geral mostram valores reais (não zeros)
3. Verifique se os títulos das demandas são reais (não "Demanda #N")
4. Confirme que o gráfico de barras da Visão Geral está ordenado por fase_ordem
5. Verifique se a tabela de Demandas tem as 11 colunas com formatação condicional
6. Confirme que a atualização automática está ativa (ícone de relógio no dataset)
7. Acesse https://eblsolucoescorporativas.com/ e confirme que a aba Power BI mostra o dashboard

Tire screenshots de cada página e confirme que o visual está idêntico ao site EBL:
- Fundo escuro #0d1117 ✓
- Cards com bordas coloridas ✓
- Gráficos com paleta EBL (ciano, verde, amarelo, vermelho) ✓
- Títulos em ciano #00d4ff ✓
- Texto em #e6edf3 ✓

Relate qualquer divergência encontrada.
```

---

## RESUMO DO QUE O CLAUDE DEVE ENTREGAR

| Página | Visuais | Status esperado |
|---|---|---|
| Visão Geral | 8 cards KPI + 2 gráficos + 1 tabela status | Completo, dark, dados reais |
| Pipeline | 1 funil + 1 barras + 1 tabela atrasos | Completo, ordenado por fase |
| Projetos | 4 filtros + 1 tabela com formatação | Completo, filtrável |
| Equipe | 2 gráficos + 1 tabela resumo | Completo, por responsável |
| Financeiro | 4 cards + 2 gráficos + 1 tabela | Completo, R$ formatado |
| Demandas | 1 busca + 3 filtros + 1 tabela mestre | Completo, 11 colunas |

**Resultado final esperado:** Dashboard Power BI visualmente idêntico ao site eblsolucoescorporativas.com, com atualização automática a cada hora via script Python integrado ao Kanboard.

---

*Documento gerado em: 10/04/2026 | Versão: 2.0 | Repositório: ErickBrendal/kanboard*
