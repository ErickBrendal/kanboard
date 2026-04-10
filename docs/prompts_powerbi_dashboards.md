# Prompts para Construção dos Dashboards Power BI — EBL Soluções Corporativas

> **Como usar:** Abra o Power BI Desktop ou acesse `https://app.powerbi.com`, ative a extensão do Claude e cole cada prompt na sequência indicada. Execute um prompt por vez e aguarde a confirmação antes de avançar.

---

## CONTEXTO GERAL (leia antes de executar qualquer prompt)

**Objetivo:** Construir um conjunto de dashboards no Power BI que replique e expanda a estrutura do Dashboard Executivo em `https://eblsolucoescorporativas.com/`, integrando dados em tempo real do Kanboard.

**Identidade Visual EBL:**
- Fundo: `#0d1117` (preto azulado escuro)
- Cor primária: `#00d4ff` (ciano elétrico)
- Cor secundária: `#f59e0b` (âmbar/dourado)
- Cor de sucesso: `#10b981` (verde esmeralda)
- Cor de alerta: `#ef4444` (vermelho)
- Cor de aviso: `#f59e0b` (amarelo)
- Fonte: Segoe UI (padrão Power BI) — negrito para títulos, regular para dados
- Bordas dos cards: coloridas por categoria (ciano, verde, amarelo, vermelho)
- Estilo: dark mode, minimalista, dados em destaque

**Dataset Power BI:**
- Nome: `EBL Fast Track Salesforce`
- Dataset ID: `39d50fe5-cde9-4244-b5e5-422a73e8e142`
- Workspace: My Workspace
- Usuário: `admebl@eblsolucoescorporativas.com`

**Tabelas disponíveis no dataset:**

| Tabela | Colunas principais |
|---|---|
| `Demandas` | id, titulo, fase, fase_ordem, status, status_id, coluna, responsavel, responsavel_id, prioridade, area, tipo, valor, horas, tempo_gasto, complexidade, data_criacao, data_vencimento, data_conclusao, prazo_status, score, descricao, projeto_id, categoria_id, swimlane_id, criador_id, posicao |
| `Fases` | (fase, contagem por fase) |
| `KPIs` | (indicadores calculados: total, implementadas, em andamento, etc.) |
| `Responsaveis` | (responsavel, contagem de demandas) |

**Sincronização automática:** O script `sync_powerbi_v4.py` atualiza o dataset via API REST a cada execução. Os dados são empurrados via Push Dataset (streaming).

---

## PROMPT 1 — Criar Medidas DAX Fundamentais

```
Preciso que você crie as medidas DAX no dataset "EBL Fast Track Salesforce" no Power BI.

ACESSO:
- URL: https://app.powerbi.com
- Usuário: admebl@eblsolucoescorporativas.com
- Senha: Senha@2026
- Dataset: EBL Fast Track Salesforce (ID: 39d50fe5-cde9-4244-b5e5-422a73e8e142)

TABELA BASE: Demandas

Crie as seguintes medidas DAX na tabela Demandas:

1. Total de Demandas
   DAX: [Total Demandas] = COUNTROWS(Demandas)

2. Implementadas (Concluídas)
   DAX: [Implementadas] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "10. Concluído")

3. Em Andamento
   DAX: [Em Andamento] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] IN {"07. Em Desenvolvimento", "08. Testes", "09. Hypercare"})

4. No Backlog
   DAX: [No Backlog] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] IN {"01. Ideação / POC", "02. Novo", "03. Backlog"})

5. Alta Prioridade
   DAX: [Alta Prioridade] = CALCULATE(COUNTROWS(Demandas), Demandas[prioridade] = 3)

6. Bloqueadas / On Hold
   DAX: [Bloqueadas] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "11. On Hold")

7. Canceladas
   DAX: [Canceladas] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "12. Cancelado")

8. % Conclusão
   DAX: [Pct Conclusao] = DIVIDE([Implementadas], [Total Demandas], 0)

9. Valor Total do Portfólio
   DAX: [Valor Total] = SUM(Demandas[valor])

10. Horas Estimadas Total
    DAX: [Horas Total] = SUM(Demandas[horas])

11. Horas Gastas Total
    DAX: [Horas Gastas] = SUM(Demandas[tempo_gasto])

12. % Evolução Média
    DAX: [Evolucao Media] = AVERAGE(Demandas[score])

13. Demandas Atrasadas
    DAX: [Atrasadas] = CALCULATE(COUNTROWS(Demandas), Demandas[prazo_status] = "atrasado", Demandas[status_id] = 1)

14. Demandas Pendente Aprovação
    DAX: [Pendente Aprovacao] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] = "06. Pendente Aprovação")

15. Demandas em Análise/Planejamento
    DAX: [Em Analise] = CALCULATE(COUNTROWS(Demandas), Demandas[fase] IN {"04. Análise TI", "05. Planejamento"})

Após criar todas as medidas, confirme listando os nomes de todas as medidas criadas com sucesso.
```

---

## PROMPT 2 — Criar Página 1: Visão Geral (KPI Cards)

```
Agora crie a primeira página do relatório Power BI chamada "📊 Visão Geral" com o seguinte layout de cards KPI.

ACESSO POWER BI:
- URL: https://app.powerbi.com
- Usuário: admebl@eblsolucoescorporativas.com
- Senha: Senha@2026
- Dataset: EBL Fast Track Salesforce

IDENTIDADE VISUAL:
- Fundo da página: #0d1117 (preto azulado)
- Fonte: Segoe UI
- Modo: Dark Theme

ESTRUTURA DA PÁGINA (layout em grade 4x2):

LINHA 1 — 4 cards grandes (KPIs principais):

Card 1 — TOTAL DE DEMANDAS
  - Medida: [Total Demandas]
  - Cor da borda/título: #00d4ff (ciano)
  - Ícone: gráfico de barras
  - Subtítulo: "Portfólio ativo"

Card 2 — IMPLEMENTADAS
  - Medida: [Implementadas]
  - Cor da borda/título: #10b981 (verde)
  - Subtítulo: "[Pct Conclusao] de conclusão"
  - Ícone: check verde

Card 3 — EM ANDAMENTO
  - Medida: [Em Andamento]
  - Cor da borda/título: #f59e0b (âmbar)
  - Subtítulo: "Dev + Testes + Hypercare"
  - Ícone: raio/lightning

Card 4 — ALTA PRIORIDADE
  - Medida: [Alta Prioridade]
  - Cor da borda/título: #ef4444 (vermelho)
  - Subtítulo: "Atenção imediata"
  - Ícone: círculo vermelho

LINHA 2 — 4 cards médios:

Card 5 — NO BACKLOG
  - Medida: [No Backlog]
  - Cor: #6366f1 (roxo/índigo)
  - Subtítulo: "Ideação + Novo + Backlog"

Card 6 — BLOQUEADAS
  - Medida: [Bloqueadas]
  - Cor: #f59e0b (âmbar)
  - Subtítulo: "On Hold / Impedimento"

Card 7 — CANCELADAS
  - Medida: [Canceladas]
  - Cor: #6b7280 (cinza)
  - Subtítulo: "Fora do escopo"

Card 8 — VALOR DO PORTFÓLIO
  - Medida: [Valor Total]
  - Formato: R$ #,##0
  - Cor: #10b981 (verde)
  - Subtítulo: "Investimento estimado"

LINHA 3 — 2 gráficos lado a lado:

Gráfico Esquerdo — "Distribuição por Fase"
  - Tipo: Gráfico de barras horizontais
  - Eixo Y: Demandas[fase]
  - Valores: COUNTROWS(Demandas) por fase
  - Cores: gradiente de #00d4ff para #10b981
  - Ordenar por: fase_ordem (crescente)
  - Fundo: #161b22

Gráfico Direito — "Por Prioridade"
  - Tipo: Gráfico de rosca (donut)
  - Legenda: Demandas[prioridade] (1=Baixa, 2=Média, 3=Alta)
  - Valores: COUNTROWS(Demandas)
  - Cores: 1=#10b981, 2=#f59e0b, 3=#ef4444
  - Fundo: #161b22

RODAPÉ — Linha de status (4 mini-cards):
  - Abertas: [Total Demandas] - [Canceladas] - [Implementadas]
  - Em Progresso: [Em Andamento]
  - Implementadas: [Implementadas]
  - % Conclusão: [Pct Conclusao] (formato percentual)

Aplique o tema dark em toda a página: fundo #0d1117, texto branco, sem bordas brancas.
```

---

## PROMPT 3 — Criar Página 2: Pipeline (Funil de Fases)

```
Crie a segunda página do relatório chamada "🔄 Pipeline" no Power BI.

OBJETIVO: Mostrar o fluxo de demandas através das 12 fases do pipeline.

DATASET: EBL Fast Track Salesforce
TEMA: Dark (#0d1117)

ESTRUTURA:

Seção 1 — "Fluxo do Pipeline" (largura total)
  - Tipo de visual: Gráfico de funil (Funnel chart) OU Gráfico de barras empilhadas horizontais
  - Dados: Contagem de demandas por fase, na ordem:
    1. Ideação / POC
    2. Novo
    3. Backlog
    4. Análise TI
    5. Planejamento
    6. Pendente Aprovação
    7. Em Desenvolvimento
    8. Testes
    9. Hypercare
    10. Concluído
    11. On Hold
    12. Cancelado
  - Ordenação: por fase_ordem (campo numérico)
  - Cores por fase:
    - Ideação/POC: #8b5cf6 (roxo)
    - Novo: #3b82f6 (azul)
    - Backlog: #6366f1 (índigo)
    - Análise TI: #06b6d4 (ciano escuro)
    - Planejamento: #0ea5e9 (azul claro)
    - Pendente Aprovação: #f59e0b (âmbar)
    - Em Desenvolvimento: #f97316 (laranja)
    - Testes: #eab308 (amarelo)
    - Hypercare: #84cc16 (verde lima)
    - Concluído: #10b981 (verde)
    - On Hold: #6b7280 (cinza)
    - Cancelado: #ef4444 (vermelho)
  - Mostrar rótulo de dados com contagem e percentual do total
  - Fundo: #161b22

Seção 2 — "Distribuição Detalhada" (largura total)
  - Tipo: Gráfico de barras verticais agrupadas
  - Eixo X: Demandas[fase] (ordenado por fase_ordem)
  - Eixo Y: COUNTROWS(Demandas)
  - Legenda: Demandas[prioridade]
  - Cores: prioridade 1=verde, 2=âmbar, 3=vermelho
  - Mostrar linha de tendência
  - Fundo: #161b22

Seção 3 — "Tempo Médio por Fase" (metade da largura)
  - Tipo: Gráfico de barras horizontais
  - Dados: Média de (data_conclusao - data_criacao) em dias, por fase
  - Apenas fases com status_id = 0 (concluídas)
  - Cor: #00d4ff

Seção 4 — "Demandas Atrasadas" (metade da largura)
  - Tipo: Tabela simples
  - Colunas: titulo, fase, responsavel, data_vencimento, prazo_status
  - Filtro: prazo_status = "atrasado" AND status_id = 1
  - Formatação condicional: linha vermelha para atrasadas
  - Ordenar por: data_vencimento (crescente)
  - Fundo: #161b22

Aplique fundo #0d1117 em toda a página.
```

---

## PROMPT 4 — Criar Página 3: Portfólio de Projetos

```
Crie a terceira página do relatório chamada "🗂️ Projetos" no Power BI.

OBJETIVO: Visão gerencial do portfólio completo de projetos com filtros interativos.

DATASET: EBL Fast Track Salesforce
TEMA: Dark (#0d1117)

ESTRUTURA:

BARRA DE FILTROS (topo da página — faixa horizontal):
  - Filtro 1: Seletor de Fase (Demandas[fase]) — múltipla seleção
  - Filtro 2: Seletor de Responsável (Demandas[responsavel]) — múltipla seleção
  - Filtro 3: Seletor de Prioridade (Demandas[prioridade]) — múltipla seleção
  - Filtro 4: Seletor de Área (Demandas[area]) — múltipla seleção
  - Estilo dos filtros: fundo #161b22, texto branco, borda #00d4ff

PAINEL ESQUERDO (30% da largura) — KPIs filtrados:
  - Card: Total filtrado = COUNTROWS(Demandas) com filtro aplicado
  - Card: Valor filtrado = SUM(Demandas[valor]) com filtro
  - Card: Horas filtradas = SUM(Demandas[horas]) com filtro
  - Gráfico de rosca: distribuição por fase das demandas filtradas

PAINEL DIREITO (70% da largura) — Tabela de demandas:
  - Tipo: Tabela interativa (Matrix ou Table visual)
  - Colunas:
    # | Título | Fase | Responsável | Prioridade | Valor (R$) | Horas | Data Criação | Vencimento | Status Prazo
  - Formatação condicional:
    - Coluna "Fase": cor de fundo por fase (mesmas cores do Pipeline)
    - Coluna "Prioridade": 1=verde, 2=âmbar, 3=vermelho
    - Coluna "Status Prazo": atrasado=vermelho, no prazo=verde, sem prazo=cinza
  - Paginação: 20 linhas por página
  - Ordenação padrão: fase_ordem crescente, depois data_criacao decrescente
  - Fundo: #161b22
  - Cabeçalho: fundo #1f2937, texto #00d4ff

RODAPÉ:
  - Texto: "Última atualização: [data/hora do último refresh]"
  - Cor: #6b7280

Aplique fundo #0d1117 em toda a página.
```

---

## PROMPT 5 — Criar Página 4: Equipe e Responsáveis

```
Crie a quarta página do relatório chamada "👥 Equipe" no Power BI.

OBJETIVO: Análise de carga de trabalho e performance por responsável.

DATASET: EBL Fast Track Salesforce
TEMA: Dark (#0d1117)

ESTRUTURA:

LINHA 1 — Cards por responsável (um card por pessoa):
Para cada responsável único em Demandas[responsavel], criar um card com:
  - Nome do responsável (título do card)
  - Total de demandas atribuídas
  - Demandas em andamento
  - Demandas concluídas
  - % de conclusão individual
  - Borda colorida: usar cor única por responsável (sequência: #00d4ff, #10b981, #f59e0b, #8b5cf6, #ef4444)

LINHA 2 — Gráficos de análise:

Gráfico Esquerdo (50%) — "Carga de Trabalho por Responsável"
  - Tipo: Gráfico de barras horizontais empilhadas
  - Eixo Y: Demandas[responsavel]
  - Segmentos: contagem por fase (agrupadas em: Backlog, Em Andamento, Concluído, Bloqueado)
  - Cores: Backlog=#6366f1, Em Andamento=#f59e0b, Concluído=#10b981, Bloqueado=#6b7280
  - Fundo: #161b22

Gráfico Direito (50%) — "Horas por Responsável"
  - Tipo: Gráfico de barras verticais
  - Eixo X: Demandas[responsavel]
  - Eixo Y primário: SUM(Demandas[horas]) — barras azuis (#00d4ff)
  - Eixo Y secundário: SUM(Demandas[tempo_gasto]) — linha verde (#10b981)
  - Legenda: "Estimado vs Realizado"
  - Fundo: #161b22

LINHA 3 — Tabela detalhada por responsável:
  - Tipo: Matrix
  - Linhas: Demandas[responsavel]
  - Colunas: Demandas[fase]
  - Valores: COUNTROWS(Demandas)
  - Totais de linha e coluna habilitados
  - Formatação condicional por intensidade de cor (heatmap): quanto mais demandas, mais intenso o azul (#00d4ff)
  - Fundo: #161b22

Aplique fundo #0d1117 em toda a página.
```

---

## PROMPT 6 — Criar Página 5: Análise Financeira e ROI

```
Crie a quinta página do relatório chamada "💰 Financeiro" no Power BI.

OBJETIVO: Visão financeira do portfólio — valor investido, ROI e distribuição por área.

DATASET: EBL Fast Track Salesforce
TEMA: Dark (#0d1117)

ESTRUTURA:

LINHA 1 — 4 KPI Cards financeiros:

Card 1 — VALOR TOTAL DO PORTFÓLIO
  - Medida: [Valor Total] = SUM(Demandas[valor])
  - Formato: R$ #,##0.00
  - Cor: #10b981 (verde)

Card 2 — VALOR EM ANDAMENTO
  - Medida: CALCULATE(SUM(Demandas[valor]), Demandas[status_id] = 1)
  - Formato: R$ #,##0.00
  - Cor: #f59e0b (âmbar)

Card 3 — VALOR CONCLUÍDO
  - Medida: CALCULATE(SUM(Demandas[valor]), Demandas[fase] = "10. Concluído")
  - Formato: R$ #,##0.00
  - Cor: #00d4ff (ciano)

Card 4 — HORAS TOTAIS ESTIMADAS
  - Medida: [Horas Total] = SUM(Demandas[horas])
  - Formato: #,##0 "h"
  - Cor: #8b5cf6 (roxo)

LINHA 2 — Gráficos de distribuição financeira:

Gráfico Esquerdo (50%) — "Valor por Área"
  - Tipo: Gráfico de barras horizontais
  - Eixo Y: Demandas[area]
  - Eixo X: SUM(Demandas[valor])
  - Formato de valor: R$ #,##0
  - Ordenar por valor decrescente
  - Cores: gradiente de #00d4ff para #0ea5e9
  - Fundo: #161b22

Gráfico Direito (50%) — "Distribuição por Tipo"
  - Tipo: Gráfico de rosca (donut)
  - Legenda: Demandas[tipo]
  - Valores: SUM(Demandas[valor])
  - Mostrar percentual e valor absoluto
  - Fundo: #161b22

LINHA 3 — Gráfico de evolução temporal:

"Evolução do Portfólio ao Longo do Tempo"
  - Tipo: Gráfico de área empilhada
  - Eixo X: Demandas[data_criacao] (agrupado por mês)
  - Eixo Y: COUNTROWS(Demandas) acumulado
  - Séries: Criadas vs Concluídas
  - Cores: Criadas=#00d4ff, Concluídas=#10b981
  - Fundo: #161b22

LINHA 4 — Tabela financeira detalhada:
  - Colunas: Título | Área | Tipo | Valor (R$) | Horas | Fase | Responsável
  - Ordenar por: Valor decrescente
  - Formatação: valor em verde se concluído, âmbar se em andamento, cinza se backlog
  - Fundo: #161b22

Aplique fundo #0d1117 em toda a página.
```

---

## PROMPT 7 — Criar Página 6: Demandas Detalhadas (Tabela Mestre)

```
Crie a sexta página do relatório chamada "📋 Demandas" no Power BI.

OBJETIVO: Tabela mestre com todas as demandas, filtros avançados e exportação.

DATASET: EBL Fast Track Salesforce
TEMA: Dark (#0d1117)

ESTRUTURA:

BARRA DE PESQUISA E FILTROS (topo):
  - Campo de busca por título (Q&A ou slicer de texto)
  - Filtro: Fase (múltipla seleção, com ícone de cor por fase)
  - Filtro: Responsável (múltipla seleção)
  - Filtro: Prioridade (1, 2, 3 com ícones coloridos)
  - Filtro: Status Prazo (no prazo / atrasado / sem prazo)
  - Filtro: Período de criação (date range slicer)
  - Botão "Limpar Filtros" (bookmark action)

TABELA PRINCIPAL (largura total):
  - Tipo: Table visual com formatação condicional avançada
  - Colunas e formatação:

  | Coluna | Largura | Formatação |
  |---|---|---|
  | # (id) | 50px | texto cinza |
  | Título | 300px | texto branco, negrito |
  | Fase | 150px | badge colorido por fase |
  | Responsável | 120px | texto ciano |
  | Prioridade | 80px | ícone: 🔴 Alta / 🟡 Média / 🟢 Baixa |
  | Área | 120px | texto cinza claro |
  | Valor (R$) | 100px | verde se > 0, cinza se 0 |
  | Horas | 70px | texto branco |
  | Criação | 90px | formato dd/MM/yyyy |
  | Vencimento | 90px | vermelho se atrasado |
  | Prazo | 80px | badge: 🔴 Atrasado / 🟢 No Prazo / ⚪ S/ Prazo |

  - Paginação: 25 linhas por página
  - Linhas alternadas: #161b22 e #1f2937
  - Cabeçalho: fundo #0d1117, texto #00d4ff, negrito
  - Hover: linha destacada em #1e3a5f

RODAPÉ:
  - Total de registros filtrados: "Exibindo X de Y demandas"
  - Botão de exportação para Excel (se disponível no Power BI Service)

Aplique fundo #0d1117 em toda a página.
```

---

## PROMPT 8 — Configurar Atualização Automática e Publicar

```
Agora configure a atualização automática do dataset e publique o relatório no Power BI Service.

ACESSO:
- URL: https://app.powerbi.com
- Usuário: admebl@eblsolucoescorporativas.com
- Senha: Senha@2026
- Dataset: EBL Fast Track Salesforce (ID: 39d50fe5-cde9-4244-b5e5-422a73e8e142)

PASSO 1 — Configurar atualização agendada do dataset:
1. Acesse o dataset "EBL Fast Track Salesforce" em My Workspace
2. Clique em "Settings" (Configurações)
3. Em "Scheduled refresh", habilite a atualização
4. Configure para atualizar a cada 1 hora (ou no máximo permitido pelo plano)
5. Fuso horário: America/Sao_Paulo (UTC-3)
6. Horários: 08:00, 09:00, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 16:00, 17:00, 18:00
7. Salve as configurações

PASSO 2 — Criar um Dashboard no Power BI Service:
1. Acesse "My Workspace"
2. Clique em "+ New" > "Dashboard"
3. Nome: "EBL — Portfólio TI | Dashboard Executivo"
4. Fixe os seguintes visuais do relatório neste dashboard:
   - Card "Total de Demandas" (da página Visão Geral)
   - Card "Implementadas" (da página Visão Geral)
   - Card "Em Andamento" (da página Visão Geral)
   - Card "Alta Prioridade" (da página Visão Geral)
   - Gráfico "Distribuição por Fase" (da página Visão Geral)
   - Gráfico "Carga de Trabalho por Responsável" (da página Equipe)
5. Organize os tiles no dashboard em layout 2x3

PASSO 3 — Configurar tema do dashboard:
1. No dashboard, clique em "..." > "Dashboard settings"
2. Em "Theme", selecione "Dark" ou aplique o tema personalizado:
   - Background: #0d1117
   - Tile background: #161b22
   - Font color: #ffffff
   - Accent color: #00d4ff

PASSO 4 — Gerar link de incorporação (embed):
1. No dashboard, clique em "File" > "Embed report" > "Website or portal"
2. Copie o link de incorporação gerado
3. Informe o link para que possa ser adicionado ao site eblsolucoescorporativas.com

PASSO 5 — Compartilhar acesso:
1. No workspace, clique em "Manage access"
2. Adicione: erick@eblsolucoescorporativas.com com permissão "Viewer"
3. Habilite "Allow recipients to share this report"

Confirme cada passo executado e informe o link de incorporação ao final.
```

---

## PROMPT 9 — Criar Tema Personalizado (JSON)

```
Aplique o tema personalizado EBL em todo o relatório Power BI.

Crie um arquivo de tema JSON com o seguinte conteúdo e importe no relatório:

{
  "name": "EBL Dark Theme",
  "dataColors": [
    "#00d4ff",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#6366f1",
    "#f97316",
    "#06b6d4",
    "#84cc16",
    "#ec4899"
  ],
  "background": "#0d1117",
  "foreground": "#ffffff",
  "tableAccent": "#00d4ff",
  "visualStyles": {
    "*": {
      "*": {
        "background": [{"color": {"solid": {"color": "#161b22"}}}],
        "border": [{"show": true, "color": {"solid": {"color": "#30363d"}}}],
        "title": {
          "fontColor": [{"solid": {"color": "#ffffff"}}],
          "background": [{"solid": {"color": "#0d1117"}}]
        }
      }
    },
    "card": {
      "*": {
        "calloutValue": [{"fontColor": {"solid": {"color": "#00d4ff"}}, "fontSize": [32]}],
        "label": [{"fontColor": {"solid": {"color": "#9ca3af"}}}]
      }
    },
    "page": {
      "*": {
        "background": [{"color": {"solid": {"color": "#0d1117"}}, "transparency": 0}]
      }
    }
  }
}

COMO IMPORTAR:
1. No Power BI Desktop ou Service, vá em "View" > "Themes" > "Browse for themes"
2. Selecione o arquivo JSON acima
3. Aplique em todas as páginas do relatório

Após importar, verifique se todas as páginas estão com o fundo #0d1117 e confirme.
```

---

## PROMPT 10 — Integrar com o Site EBL (embed)

```
O objetivo final é integrar o relatório Power BI ao site https://eblsolucoescorporativas.com/ na aba "🔌 Power BI".

CONTEXTO DO SITE:
- O site é um dashboard React hospedado no servidor Oracle Cloud (150.230.88.196)
- Repositório: https://github.com/ErickBrendal/kanboard (pasta /site ou /dashboard)
- Acesso SSH: usuário ubuntu, chave em ~/.ssh/oracle_kanboard.pem

PASSO 1 — Obter o link de incorporação do Power BI:
1. Acesse https://app.powerbi.com
2. Abra o relatório "EBL — Portfólio TI | Dashboard Executivo"
3. Clique em "File" > "Embed report" > "Publish to web (public)" OU "Website or portal"
4. Copie o código iframe gerado

PASSO 2 — Atualizar o componente PowerBI no site:
No arquivo do site que contém a aba "🔌 Power BI", substitua o conteúdo atual pelo iframe do Power BI:

```html
<div style="width: 100%; height: 800px; border: none;">
  <iframe
    title="EBL Portfólio TI"
    src="[COLE_O_LINK_DO_EMBED_AQUI]"
    frameborder="0"
    allowFullScreen="true"
    style="width: 100%; height: 100%; border: none;"
  ></iframe>
</div>
```

PASSO 3 — Se o relatório exigir autenticação:
Use o Power BI Embedded com token de serviço:
- Tenant ID: 208364c6-eee7-4324-ac4a-d45fe452a1bd
- Client ID: 1950a258-227b-4e31-a9cf-717495945fc2
- Dataset ID: 39d50fe5-cde9-4244-b5e5-422a73e8e142
- Report ID: (obter após publicar o relatório)

PASSO 4 — Fazer deploy no servidor:
Após atualizar o código, execute no servidor:
```bash
ssh -i ~/.ssh/oracle_kanboard.pem ubuntu@150.230.88.196
cd /opt/kanboard  # ou onde o site está hospedado
git pull origin main
pm2 restart all  # ou docker-compose restart
```

Confirme quando o iframe estiver funcionando em https://eblsolucoescorporativas.com/ na aba Power BI.
```

---

## RESUMO DA SEQUÊNCIA DE EXECUÇÃO

| Ordem | Prompt | O que faz | Tempo estimado |
|---|---|---|---|
| 1 | Medidas DAX | Cria 15 medidas calculadas | 10 min |
| 2 | Página Visão Geral | 8 KPI cards + 2 gráficos | 20 min |
| 3 | Página Pipeline | Funil + distribuição + tabela atrasadas | 20 min |
| 4 | Página Projetos | Filtros + tabela interativa | 15 min |
| 5 | Página Equipe | Cards por responsável + heatmap | 20 min |
| 6 | Página Financeiro | KPIs financeiros + gráficos | 15 min |
| 7 | Página Demandas | Tabela mestre com filtros avançados | 15 min |
| 8 | Publicar e agendar | Atualização automática + dashboard | 10 min |
| 9 | Tema JSON | Aplicar identidade visual EBL | 5 min |
| 10 | Integrar ao site | Embed no eblsolucoescorporativas.com | 10 min |

**Total estimado: ~2 horas**

---

## NOTAS IMPORTANTES

1. **Ordem obrigatória:** Execute sempre o Prompt 1 (medidas DAX) antes dos demais, pois os visuais dependem das medidas.

2. **Dados em tempo real:** O dataset é alimentado via Push API pelo script `sync_powerbi_v4.py`. Para dados atualizados, execute o script antes de criar os visuais.

3. **Limitação do plano gratuito:** O Power BI Free não permite compartilhamento público. Se necessário, use o Power BI Pro (trial de 60 dias disponível na conta) ou o recurso "Publish to web" para embed público.

4. **Campos de tags:** Os campos de tags do Kanboard (área, subcategoria, etc.) são armazenados como metadados via metaMagik e estão disponíveis no campo `area` e `tipo` da tabela Demandas.

5. **Rollback:** Antes de fazer alterações no relatório existente, salve uma cópia com o nome "EBL Fast Track Salesforce - BACKUP [data]".
