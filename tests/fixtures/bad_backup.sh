#!/bin/bash
set -euo pipefail

REMOTE="offsite:mybucket"

if ! rclone lsd "$REMOTE" >/dev/null 2>&1; then
    echo "ERROR: remote '$REMOTE' no está configurado todavía. Ejecuta setup.sh"
fi

rsync -a /data/ /mnt/local-mirror/
