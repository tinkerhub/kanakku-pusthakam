#!/bin/sh
set -eu

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

api_url="${TENANT_API_URL:-${VITE_API_URL:-/api}}"
tenant_token="${TENANT_TOKEN:-${VITE_TENANT_TOKEN:-}}"

cat > /usr/share/nginx/html/config.js <<EOF
window.__TENANT__ = {
  apiUrl: "$(json_escape "$api_url")",
  tenantToken: "$(json_escape "$tenant_token")"
};
EOF
