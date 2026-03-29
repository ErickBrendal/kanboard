# Integração Kanboard → Power BI
## EBL Soluções Corporativas — Fast Track Salesforce

---

## 1. Visão Geral

O Kanboard expõe uma **API JSON-RPC** que o Power BI pode consumir diretamente via **Web Connector** ou via **script Python/R** no Power Query. Esta documentação cobre as duas abordagens.

---

## 2. Credenciais da API

| Campo         | Valor                                                              |
|---------------|--------------------------------------------------------------------|
| **URL Base**  | `http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php`              |
| **Usuário**   | `admin`                                                            |
| **Token API** | `a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff`   |
| **Auth**      | HTTP Basic — usuário: `admin`, senha: token acima                  |

---

## 3. Endpoints Principais para Power BI

### 3.1 Listar Todas as Tarefas (Abertas)
```json
POST /jsonrpc.php
{
  "jsonrpc": "2.0",
  "method": "getAllTasks",
  "id": 1,
  "params": {
    "project_id": 11,
    "status_id": 1
  }
}
```

### 3.2 Listar Tarefas Fechadas (Implementadas)
```json
{
  "jsonrpc": "2.0",
  "method": "getAllTasks",
  "id": 1,
  "params": {
    "project_id": 11,
    "status_id": 0
  }
}
```

### 3.3 Listar Todos os Projetos
```json
{
  "jsonrpc": "2.0",
  "method": "getAllProjects",
  "id": 1
}
```

### 3.4 Listar Colunas do Projeto
```json
{
  "jsonrpc": "2.0",
  "method": "getColumns",
  "id": 1,
  "params": {"project_id": 11}
}
```

---

## 4. Script Power Query (M Language)

Cole este código no Power BI → **Obter Dados → Consulta em Branco → Editor Avançado**:

```m
let
    // Configurações
    BaseUrl = "http://kanboard.eblsolucoescorp.tec.br/jsonrpc.php",
    ApiToken = "a43a8785a4487979964cd7e12fc8c56bbb6ef7a6fa64bcb6c45fa1afc6ff",
    ProjectId = 11,
    
    // Credenciais Base64
    Credentials = Binary.ToText(Text.ToBinary("admin:" & ApiToken), BinaryEncoding.Base64),
    
    // Função para chamar a API
    CallApi = (method as text, params as record) =>
        let
            Body = Json.FromValue([
                jsonrpc = "2.0",
                method = method,
                id = 1,
                params = params
            ]),
            Response = Web.Contents(BaseUrl, [
                Headers = [
                    #"Content-Type" = "application/json",
                    #"Authorization" = "Basic " & Credentials
                ],
                Content = Body
            ]),
            Json = Json.Document(Response)
        in
            Json[result],
    
    // Buscar tarefas abertas
    TarefasAbertas = CallApi("getAllTasks", [project_id = ProjectId, status_id = 1]),
    
    // Buscar tarefas fechadas
    TarefasFechadas = CallApi("getAllTasks", [project_id = ProjectId, status_id = 0]),
    
    // Buscar colunas
    Colunas = CallApi("getColumns", [project_id = ProjectId]),
    ColunasTable = Table.FromList(Colunas, Splitter.SplitByNothing()),
    ColunasExpanded = Table.ExpandRecordColumn(ColunasTable, "Column1", {"id", "title"}),
    
    // Combinar tarefas
    TodasTarefas = List.Combine({TarefasAbertas, TarefasFechadas}),
    
    // Converter para tabela
    TarefasTable = Table.FromList(TodasTarefas, Splitter.SplitByNothing()),
    TarefasExpanded = Table.ExpandRecordColumn(TarefasTable, "Column1", {
        "id", "title", "column_id", "swimlane_id", "is_active",
        "priority", "color_id", "date_due", "date_creation",
        "date_modification", "date_completed", "description"
    }),
    
    // Adicionar nome da coluna (fase)
    ColunasMap = Record.FromList(
        List.Transform(Colunas, each _[title]),
        List.Transform(Colunas, each Text.From(_[id]))
    ),
    
    TarefasComFase = Table.AddColumn(TarefasExpanded, "Fase", each 
        try Record.Field(ColunasMap, Text.From([column_id])) otherwise "Desconhecida"
    ),
    
    // Converter tipos
    TarefasFinais = Table.TransformColumnTypes(TarefasComFase, {
        {"id", Int64.Type},
        {"column_id", Int64.Type},
        {"priority", Int64.Type},
        {"is_active", type logical}
    }),
    
    // Adicionar coluna de Status
    TarefasComStatus = Table.AddColumn(TarefasFinais, "Status", each 
        if [is_active] = true then "Aberta" else "Fechada"
    ),
    
    // Adicionar coluna de Prioridade Texto
    TarefasComPrioridade = Table.AddColumn(TarefasComStatus, "Prioridade_Texto", each 
        if [priority] = 3 then "Alta"
        else if [priority] = 2 then "Média"
        else "Baixa"
    )
    
in
    TarefasComPrioridade
```

---

## 5. Medidas DAX Recomendadas

```dax
// Total de Demandas
Total Demandas = COUNTROWS(Tarefas)

// Demandas por Fase
Demandas por Fase = 
CALCULATE(
    COUNTROWS(Tarefas),
    ALLEXCEPT(Tarefas, Tarefas[Fase])
)

// % Concluído
% Concluido = 
DIVIDE(
    CALCULATE(COUNTROWS(Tarefas), Tarefas[Fase] = "10. Implementado"),
    COUNTROWS(Tarefas),
    0
)

// Demandas em Atraso
Demandas em Atraso = 
CALCULATE(
    COUNTROWS(Tarefas),
    Tarefas[date_due] < TODAY(),
    Tarefas[Status] = "Aberta"
)

// Valor Total
Valor Total = SUM(Tarefas[Valor])

// Horas Totais Valtech
Horas Valtech Total = SUM(Tarefas[Horas_Valtech])
```

---

## 6. Visuais Recomendados no Power BI

| Visual              | Campos                                      | Insight                          |
|---------------------|---------------------------------------------|----------------------------------|
| Gráfico de Barras   | Fase × Contagem                             | Pipeline de demandas             |
| Gráfico de Pizza    | Responsável × Contagem                      | Distribuição por analista        |
| Matriz              | Área × Fase × Contagem                      | Visão cruzada área/fase          |
| KPI Card            | Total, Implementado, Em Andamento, Atraso   | Indicadores executivos           |
| Gráfico de Linha    | Data Criação × Contagem (acumulado)         | Evolução temporal                |
| Treemap             | Tipo de Demanda × Valor                     | Distribuição financeira          |
| Tabela Detalhada    | ID, Título, Fase, Responsável, Prazo, Valor | Drill-down operacional           |

---

## 7. Atualização Automática

Configure o **Gateway de Dados** do Power BI para atualização automática:

1. Instale o **Power BI Gateway** no servidor ou máquina com acesso ao Kanboard
2. Configure a fonte de dados com as credenciais acima
3. Defina atualização a cada **1 hora** ou conforme necessidade

---

## 8. Mapeamento de Colunas (IDs)

| ID  | Fase                  |
|-----|-----------------------|
| 165 | 01. Backlog           |
| 166 | 02. Refinamento       |
| 167 | 03. Priorizada        |
| 168 | 04. Análise           |
| 169 | 05. Estimativa        |
| 170 | 06. Aprovação         |
| 171 | 07. Desenvolvimento   |
| 172 | 08. Homologação       |
| 173 | 09. Deploy            |
| 174 | 10. Implementado      |
| 175 | 11. Cancelado         |

---

*Documentação gerada automaticamente — EBL Soluções Corporativas*
