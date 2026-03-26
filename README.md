# Kanboard EBL Soluções Corporativas — Deploy Automatizado

Este projeto contém a infraestrutura e as configurações para a implantação do Kanboard na **EBL Soluções Corporativas**.

## Estrutura do Projeto

- `docker-compose.yml`: Configuração dos containers (Kanboard, PostgreSQL, Nginx, Certbot).
- `config.php`: Configuração personalizada do Kanboard com suporte a PostgreSQL e SMTP.
- `nginx/`: Configurações do Nginx para HTTP e HTTPS.
- `css/`: Identidade visual da EBL aplicada ao Kanboard.
- `sql/`: Schema analítico para BI (Power BI).
- `scripts/`: Scripts de ETL, Setup de Boards e Backup.
- `deploy.sh`: Script de automação total do deploy no servidor.

## Como Realizar o Deploy

1. Acesse o servidor (Ubuntu 22.04/24.04).
2. Clone este repositório ou copie a pasta `kanboard-ebl` para `/opt/kanboard-ebl`.
3. Execute o script de deploy:
   ```bash
   sudo bash deploy.sh
   ```
4. O script irá configurar Docker, Firewall, SSL e os containers.
5. **Importante:** Anote a senha do banco gerada pelo script no arquivo `.env`.

## Pós-Instalação: Configuração dos Boards

Após o deploy, siga estes passos para configurar os 5 boards padrão:

1. Acesse **https://kanboard.eblsolucoescorp.tec.br**.
2. Faça login com as credenciais padrão: `admin` / `admin`.
3. **Altere a senha do administrador imediatamente.**
4. Vá em **Configurações > API** e copie o **API Token**.
5. No servidor, edite o arquivo `/opt/kanboard-ebl/scripts/setup_kanboard.py` e cole o token na variável `API_TOKEN`.
6. Execute o setup:
   ```bash
   cd /opt/kanboard-ebl
   source venv/bin/activate
   python scripts/setup_kanboard.py
   ```

## Monitoramento e Manutenção

- **Logs:** `/opt/kanboard-ebl/logs/`
- **Backups:** `/opt/kanboard-ebl/backups/` (Mantidos por 30 dias).
- **ETL:** O script de ETL roda a cada 15 minutos via cron, alimentando o schema `bi_kanboard` no PostgreSQL.
