#!/bin/sh
# Render promtail config from template, substituting ${EXCLUDE_PATTERN}
# built from /etc/promtail/exclude_ips.txt.
set -eu

EXCLUDE_FILE="/etc/promtail/exclude_ips.txt"
CONFIG_TEMPLATE="/etc/promtail/promtail-config.template.yaml"
CONFIG_OUT="/tmp/promtail-config.yaml"

build_pattern() {
    ips=$(grep -v '^#' "$EXCLUDE_FILE" 2>/dev/null \
          | grep -v '^[[:space:]]*$' \
          | tr -d '\r' \
          | tr -d ' ' \
          | sed -e 's/\./\\./g' -e 's/\*/.*/g' \
          | tr '\n' '|' \
          | sed 's/|$//')
    if [ -n "$ips" ]; then
        printf '^(%s)\\s' "$ips"
    else
        printf '^255\\.255\\.255\\.255\\s'
    fi
}

if [ -f "$EXCLUDE_FILE" ]; then
    EXCLUDE_PATTERN=$(build_pattern)
else
    EXCLUDE_PATTERN='^255\.255\.255\.255\s'
fi
export EXCLUDE_PATTERN

# sed используется, чтобы не зависеть от envsubst в Alpine-образе.
# Шаблон содержит только ${EXCLUDE_PATTERN} — одного sed достаточно.
sed "s@\${EXCLUDE_PATTERN}@${EXCLUDE_PATTERN}@g" \
    "$CONFIG_TEMPLATE" > "$CONFIG_OUT"

echo "[entrypoint] EXCLUDE_PATTERN=${EXCLUDE_PATTERN}"
echo "[entrypoint] rendered → ${CONFIG_OUT}"

exec /usr/bin/promtail -config.file="$CONFIG_OUT"
