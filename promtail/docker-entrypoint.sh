#!/bin/sh
set -e

EXCLUDE_FILE="/etc/promtail/exclude_ips.txt"
CONFIG_TEMPLATE="/etc/promtail/promtail-config.template.yaml"
CONFIG_OUT="/etc/promtail/config.yml"

if [ -f "$EXCLUDE_FILE" ] && [ -s "$EXCLUDE_FILE" ]; then
    IPS=$(grep -v '^#' "$EXCLUDE_FILE" | grep -v '^$' | sed 's/\./\\./g' | tr '\n' '|' | sed 's/|$//')
    export EXCLUDE_PATTERN="^($IPS)\\s"
else
    export EXCLUDE_PATTERN="^255\\.255\\.255\\.255\\s"
fi

sed "s@\${EXCLUDE_PATTERN}@$EXCLUDE_PATTERN@g" "$CONFIG_TEMPLATE" > "$CONFIG_OUT"

exec /usr/bin/promtail -config.file="$CONFIG_OUT"
