CREATE SCHEMA IF NOT EXISTS bi_kanboard;

-- Dimensões
CREATE TABLE IF NOT EXISTS bi_kanboard.dim_projetos (
    projeto_id INTEGER PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    area VARCHAR(100),
    descricao TEXT,
    ativo BOOLEAN DEFAULT true,
    data_criacao TIMESTAMP,
    data_sync TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bi_kanboard.dim_usuarios (
    usuario_id INTEGER PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    username VARCHAR(100),
    perfil VARCHAR(50),
    area VARCHAR(100),
    ativo BOOLEAN DEFAULT true,
    data_sync TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bi_kanboard.dim_colunas (
    coluna_id INTEGER PRIMARY KEY,
    projeto_id INTEGER REFERENCES bi_kanboard.dim_projetos(projeto_id),
    nome VARCHAR(100) NOT NULL,
    posicao INTEGER,
    data_sync TIMESTAMP DEFAULT NOW()
);

-- Fatos
CREATE TABLE IF NOT EXISTS bi_kanboard.fato_tarefas (
    tarefa_id INTEGER PRIMARY KEY,
    projeto_id INTEGER REFERENCES bi_kanboard.dim_projetos(projeto_id),
    coluna_id INTEGER REFERENCES bi_kanboard.dim_colunas(coluna_id),
    responsavel_id INTEGER REFERENCES bi_kanboard.dim_usuarios(usuario_id),
    criador_id INTEGER REFERENCES bi_kanboard.dim_usuarios(usuario_id),
    titulo TEXT,
    prioridade INTEGER,
    cor VARCHAR(50),
    swimlane VARCHAR(100),
    categoria VARCHAR(100),
    data_criacao TIMESTAMP,
    data_inicio TIMESTAMP,
    data_fim_planejada TIMESTAMP,
    data_fim_real TIMESTAMP,
    prazo_sla TIMESTAMP,
    sla_cumprido BOOLEAN,
    lead_time_dias NUMERIC(10,2),
    aging_dias INTEGER,
    status_atual VARCHAR(100),
    is_ativa BOOLEAN,
    data_sync TIMESTAMP DEFAULT NOW()
);

-- Views para Power BI
CREATE OR REPLACE VIEW bi_kanboard.vw_produtividade_equipe AS
SELECT 
    u.nome as usuario,
    p.nome as projeto,
    COUNT(t.tarefa_id) as total_concluidas,
    AVG(t.lead_time_dias) as avg_lead_time
FROM bi_kanboard.fato_tarefas t
JOIN bi_kanboard.dim_usuarios u ON t.responsavel_id = u.usuario_id
JOIN bi_kanboard.dim_projetos p ON t.projeto_id = p.projeto_id
WHERE t.is_ativa = false AND t.data_fim_real IS NOT NULL
GROUP BY u.nome, p.nome;
