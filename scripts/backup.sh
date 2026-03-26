#!/bin/bash
set -euo pipefail
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/kanboard-ebl/backups"
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup iniciado"
docker exec kanboard_db pg_dump -U kanboard kanboard | gzip > "$BACKUP_DIR/db_${DATE}.sql.gz"
docker run --rm -v kanboard_data:/data:ro -v "$BACKUP_DIR":/backup alpine tar czf "/backup/data_${DATE}.tar.gz" -C /data .
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
echo "[$(date)] Backup concluído: $(du -sh $BACKUP_DIR | cut -f1)"
