# Estrutura de Tags para o Kanboard — Portfólio TI Elgin

## Análise e Proposta de Estrutura Visual

---

## 1. Diagnóstico: Campos da Planilha vs. Kanboard

A planilha possui **20 colunas**. O Kanboard já possui nativamente: título, responsável, data de vencimento, prioridade e descrição. Os **campos faltantes** que precisam ser representados visualmente como **tags** são:

| Campo na Planilha | Tipo de Dado | Valores Únicos | Estratégia no Kanboard |
|---|---|---|---|
| Área TI | Categórico | 2 valores | **Tag** |
| Subcategoria | Categórico | 7 valores | **Tag** |
| Área Negócio | Categórico | ~18 valores (normalizado) | **Tag** |
| Classificação Risco | Categórico | 2 valores | **Tag** |
| Recurso (Interno/Externo) | Categórico | 2 valores | **Tag** |
| ROI Aprovado | Categórico | 3 valores | **Tag** |
| % Evolução Planejado | Numérico 0–100% | Faixas | **Tag** |
| % Evolução Realizado | Numérico 0–100% | Faixas | **Tag** |
| Cherwell ID | Texto livre | Único por tarefa | **Descrição / Referência externa** |
| Custo Planejado | Numérico | Variado | **Metadado (metaMagik)** |
| Custo Realizado | Numérico | Variado | **Metadado (metaMagik)** |
| Valor ROI | Numérico | Variado | **Metadado (metaMagik)** |
| Datas (GoLive, Início, Fim) | Data | Variado | **Data de vencimento nativa + Metadado** |

---

## 2. Estrutura de Tags Proposta (com Cores)

As tags são organizadas em **6 grupos visuais**, cada grupo com uma cor base distinta para fácil identificação no quadro.

---

### GRUPO 1 — Área TI (cor base: Azul escuro `#1a3a5c`)

Identifica qual torre de TI é responsável pela demanda.

| Tag | Cor Hex |
|---|---|
| `[TI] CRM Salesforce` | `#1a3a5c` |
| `[TI] Dados & Digital` | `#1a4a7a` |

---

### GRUPO 2 — Subcategoria (cor base: Azul médio `#2563eb`)

Detalha a especialidade dentro da Área TI.

| Tag | Cor Hex |
|---|---|
| `[SUB] Suporte Salesforce` | `#2563eb` |
| `[SUB] CRM Salesforce` | `#1d4ed8` |
| `[SUB] Integração` | `#3b82f6` |
| `[SUB] E-Commerce` | `#0ea5e9` |
| `[SUB] Digital` | `#0284c7` |
| `[SUB] Site e Portal` | `#0369a1` |
| `[SUB] Dados e BI` | `#075985` |

---

### GRUPO 3 — Área de Negócio (cor base: Verde `#166534`)

Identifica qual área da empresa originou a demanda.

| Tag | Cor Hex |
|---|---|
| `[NEG] Financeiro` | `#166534` |
| `[NEG] eCommerce` | `#15803d` |
| `[NEG] Comercial` | `#16a34a` |
| `[NEG] Logística` | `#22c55e` |
| `[NEG] Fiscal` | `#14532d` |
| `[NEG] Controladoria` | `#065f46` |
| `[NEG] Marketing` | `#047857` |
| `[NEG] TI` | `#059669` |
| `[NEG] Cadastros` | `#10b981` |
| `[NEG] SAC` | `#34d399` |
| `[NEG] DHO` | `#6ee7b7` |
| `[NEG] Diretoria` | `#0d9488` |
| `[NEG] Ar & Eletro` | `#0f766e` |
| `[NEG] Refrigeração` | `#115e59` |
| `[NEG] Automação` | `#134e4a` |
| `[NEG] Bens de Consumo` | `#1a7a5e` |
| `[NEG] Engenharia` | `#2d6a4f` |
| `[NEG] Prog. Materiais` | `#40916c` |

---

### GRUPO 4 — Risco (cor base: Vermelho/Amarelo)

Sinaliza o nível de risco da demanda — visibilidade imediata no quadro.

| Tag | Cor Hex |
|---|---|
| `[RISCO] Baixo` | `#16a34a` |
| `[RISCO] Médio` | `#d97706` |
| `[RISCO] Alto` | `#dc2626` |

---

### GRUPO 5 — Recurso (cor base: Roxo `#6b21a8`)

Identifica se o recurso é interno, externo ou ambos.

| Tag | Cor Hex |
|---|---|
| `[REC] Interno` | `#6b21a8` |
| `[REC] Externo` | `#7c3aed` |
| `[REC] Ambos` | `#8b5cf6` |

---

### GRUPO 6 — ROI (cor base: Laranja `#c2410c`)

Classifica o tipo de retorno esperado da demanda.

| Tag | Cor Hex |
|---|---|
| `[ROI] Qualitativo` | `#c2410c` |
| `[ROI] Legal / Mandatório` | `#b45309` |
| `[ROI] N/A` | `#78716c` |

---

### GRUPO 7 — Evolução % (cor base: Cinza/Teal)

Faixas de progresso para visualização rápida do andamento.

| Tag | Cor Hex | Critério |
|---|---|---|
| `[EVO] 0%` | `#6b7280` | 0% realizado |
| `[EVO] 1–25%` | `#0891b2` | até 25% |
| `[EVO] 26–50%` | `#0284c7` | 26 a 50% |
| `[EVO] 51–75%` | `#1d4ed8` | 51 a 75% |
| `[EVO] 76–99%` | `#7c3aed` | 76 a 99% |
| `[EVO] 100% Concluído` | `#16a34a` | 100% |

---

## 3. Regras de Aplicação por Tarefa

Cada tarefa no Kanboard deve ter **no máximo 5 tags** para não poluir visualmente:

1. **1 tag de Área TI** (obrigatória)
2. **1 tag de Subcategoria** (obrigatória)
3. **1 tag de Área Negócio** (obrigatória)
4. **1 tag de Risco** (obrigatória)
5. **1 tag de ROI ou Recurso** (conforme relevância)

As tags de **Evolução %** são opcionais e devem ser usadas apenas em tarefas em andamento (fases: Planejamento, Em Desenvolvimento, Testes, Hypercare).

---

## 4. Campos que NÃO viram tags (ficam em metadados)

Os campos abaixo têm valores numéricos ou de texto livre e devem permanecer como **metadados do metaMagik**, não como tags:

- Cherwell ID
- Custo Planejado / Realizado
- Valor ROI
- % Evolução Planejado / Realizado (valor exato)
- Datas (GoLive original, estimada, início, fim)

---

## 5. Exemplo Visual de uma Tarefa Completa

**Tarefa:** `#3 — Melhoria no fluxo de cancelamentos - Bemol`

```
Título:      Melhoria no fluxo de cancelamentos - Bemol
Status:      Pendente Aprovação
Responsável: Felipe Nascimento
Vencimento:  21/04/2026

TAGS:
  [TI] CRM Salesforce    [SUB] CRM Salesforce
  [NEG] eCommerce        [RISCO] Baixo
  [ROI] Qualitativo

METADADOS (metaMagik):
  Cherwell ID:        81643
  Custo Planejado:    R$ 15.550,00
  % Evol. Planejado:  25%
  % Evol. Realizado:  25%
  Desvio:             0%
```

---

# PROMPT PARA O CLAUDE — Configurar Tags no Kanboard

> **Instruções:** Copie o bloco abaixo e cole no Claude com a extensão ativa no navegador, com o Kanboard aberto na aba de administração de tags.

---

```
Preciso que você configure as tags globais no Kanboard acessando diretamente o site.

## ACESSO
- URL: https://kanboard.eblsolucoescorp.tec.br
- Usuário: admin
- Senha: EBL@Kanboard2026
- Página de tags globais: https://kanboard.eblsolucoescorp.tec.br/?controller=TagController&action=index

## OBJETIVO
Criar todas as tags listadas abaixo na seção de "Tags Globais" do Kanboard. Para cada tag, você deve:
1. Acessar a página de gerenciamento de tags
2. Clicar em "Adicionar tag" (ou equivalente)
3. Inserir o nome exato da tag
4. Selecionar a cor correspondente (use o color picker com o código hex)
5. Salvar

## LISTA COMPLETA DE TAGS A CRIAR

### GRUPO 1 — Área TI
- Nome: "[TI] CRM Salesforce"       | Cor: #1a3a5c
- Nome: "[TI] Dados & Digital"       | Cor: #1a4a7a

### GRUPO 2 — Subcategoria
- Nome: "[SUB] Suporte Salesforce"   | Cor: #2563eb
- Nome: "[SUB] CRM Salesforce"       | Cor: #1d4ed8
- Nome: "[SUB] Integração"           | Cor: #3b82f6
- Nome: "[SUB] E-Commerce"           | Cor: #0ea5e9
- Nome: "[SUB] Digital"              | Cor: #0284c7
- Nome: "[SUB] Site e Portal"        | Cor: #0369a1
- Nome: "[SUB] Dados e BI"           | Cor: #075985

### GRUPO 3 — Área de Negócio
- Nome: "[NEG] Financeiro"           | Cor: #166534
- Nome: "[NEG] eCommerce"            | Cor: #15803d
- Nome: "[NEG] Comercial"            | Cor: #16a34a
- Nome: "[NEG] Logística"            | Cor: #22c55e
- Nome: "[NEG] Fiscal"               | Cor: #14532d
- Nome: "[NEG] Controladoria"        | Cor: #065f46
- Nome: "[NEG] Marketing"            | Cor: #047857
- Nome: "[NEG] TI"                   | Cor: #059669
- Nome: "[NEG] Cadastros"            | Cor: #10b981
- Nome: "[NEG] SAC"                  | Cor: #34d399
- Nome: "[NEG] DHO"                  | Cor: #6ee7b7
- Nome: "[NEG] Diretoria"            | Cor: #0d9488
- Nome: "[NEG] Ar & Eletro"          | Cor: #0f766e
- Nome: "[NEG] Refrigeração"         | Cor: #115e59
- Nome: "[NEG] Automação"            | Cor: #134e4a
- Nome: "[NEG] Bens de Consumo"      | Cor: #1a7a5e
- Nome: "[NEG] Engenharia"           | Cor: #2d6a4f
- Nome: "[NEG] Prog. Materiais"      | Cor: #40916c

### GRUPO 4 — Risco
- Nome: "[RISCO] Baixo"              | Cor: #16a34a
- Nome: "[RISCO] Médio"              | Cor: #d97706
- Nome: "[RISCO] Alto"               | Cor: #dc2626

### GRUPO 5 — Recurso
- Nome: "[REC] Interno"              | Cor: #6b21a8
- Nome: "[REC] Externo"              | Cor: #7c3aed
- Nome: "[REC] Ambos"                | Cor: #8b5cf6

### GRUPO 6 — ROI
- Nome: "[ROI] Qualitativo"          | Cor: #c2410c
- Nome: "[ROI] Legal / Mandatório"   | Cor: #b45309
- Nome: "[ROI] N/A"                  | Cor: #78716c

### GRUPO 7 — Evolução %
- Nome: "[EVO] 0%"                   | Cor: #6b7280
- Nome: "[EVO] 1–25%"               | Cor: #0891b2
- Nome: "[EVO] 26–50%"              | Cor: #0284c7
- Nome: "[EVO] 51–75%"              | Cor: #1d4ed8
- Nome: "[EVO] 76–99%"              | Cor: #7c3aed
- Nome: "[EVO] 100% Concluído"      | Cor: #16a34a

## TOTAL: 40 tags a criar

## OBSERVAÇÕES IMPORTANTES
- Se o Kanboard não tiver campo de cor por hex, use o color picker mais próximo visualmente
- Tags globais ficam disponíveis para todos os projetos
- Caso a página de tags globais seja: Settings > Tags, navegue por esse caminho
- Se já existir alguma tag com nome igual, pule e não duplique
- Confirme ao final quantas tags foram criadas com sucesso

## APÓS CRIAR AS TAGS
Acesse o projeto "CRM Salesforce" (project_id=1) e aplique as tags corretas nas primeiras 5 tarefas como teste, seguindo esta lógica:
- 1 tag [TI], 1 tag [SUB], 1 tag [NEG], 1 tag [RISCO] por tarefa
- Use os dados da planilha como referência para escolher as tags corretas
```
