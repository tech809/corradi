#!/usr/bin/env bash
# Backup diario de la base de datos de CORRADI-BOT.
#
# Hace un pg_dump comprimido del contenedor corradi-db a /opt/corradi/backups y borra los
# de más de 14 días. Pensado para un cron en la instancia:
#   0 3 * * * /opt/corradi/scripts/backup_db.sh >> /tmp/corradi_backup.log 2>&1
#
# Nota: el backup queda EN LA PROPIA instancia. Protege ante corrupción/errores de datos,
# NO ante la pérdida de la máquina. Para eso, copiar además a S3 (pendiente, ver README).
set -euo pipefail

DIR="/opt/corradi/backups"
KEEP_DAYS=14
mkdir -p "$DIR"

STAMP=$(date +%Y%m%d-%H%M)
OUT="$DIR/corradi-$STAMP.sql.gz"

docker exec corradi-db pg_dump -U corradi -d corradi | gzip > "$OUT"
echo "$(date '+%F %T') backup OK -> $OUT ($(du -h "$OUT" | cut -f1))"

# Rotación: borra los backups con más de KEEP_DAYS días.
find "$DIR" -name 'corradi-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
