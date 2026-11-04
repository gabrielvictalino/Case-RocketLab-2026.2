#!/usr/bin/env bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 \
  --set portal_password="$PORTAL_ROLE_PASSWORD" \
  --set ai_password="$AI_READ_ROLE_PASSWORD" \
  --set importador_password="$IMPORTADOR_ROLE_PASSWORD" \
  --file /opt/venergy/init.sql
