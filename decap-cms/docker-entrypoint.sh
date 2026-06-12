#!/bin/sh
set -e

TENANTS_FILE=${TENANTS_FILE:-/etc/decap/tenants.json}
CONFIG_TEMPLATE=/etc/decap/config.yml.template
HTML_DIR=/usr/share/nginx/html/tenants

mkdir -p "$HTML_DIR"

require_value() {
  local value="$1"
  local name="$2"
  local slug="$3"

  if [ -z "$value" ] || [ "$value" = "null" ]; then
    echo "Missing required field '$name' for tenant '$slug'" >&2
    exit 1
  fi
}

validate_slug() {
  local slug="$1"

  case "$slug" in
    [a-z0-9]*) ;;
    *) echo "Invalid tenant slug (must start with [a-z0-9]): $slug" >&2; exit 1 ;;
  esac
  case "$slug" in
    *[!a-z0-9-]*) echo "Invalid tenant slug (only [a-z0-9-] allowed): $slug" >&2; exit 1 ;;
  esac
}

render_tenant() {
  local slug
  local gitlab_repo="$2"
  local gitlab_branch="$3"
  local gitlab_app_id="$4"
  local upload_url="$5"
  local publish_mode="${6:-simple}"
  local tenant_dir

  slug=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  tenant_dir="$HTML_DIR/$slug"

  require_value "$slug" slug "$slug"
  require_value "$gitlab_repo" gitlabRepo "$slug"
  require_value "$gitlab_branch" gitlabBranch "$slug"
  require_value "$gitlab_app_id" gitlabAppId "$slug"
  require_value "$upload_url" uploadUrl "$slug"
  validate_slug "$slug"

  mkdir -p "$tenant_dir"
  cp /usr/share/nginx/html/index.html "$tenant_dir/index.html"

  GITLAB_REPO="$gitlab_repo" GITLAB_BRANCH="$gitlab_branch" \
  GITLAB_APP_ID="$gitlab_app_id" UPLOAD_URL="$upload_url" \
  PUBLISH_MODE="$publish_mode" \
  envsubst '${GITLAB_REPO} ${GITLAB_BRANCH} ${GITLAB_APP_ID} ${UPLOAD_URL} ${PUBLISH_MODE}' \
    < "$CONFIG_TEMPLATE" > "$tenant_dir/config.yml"

  echo "  configured: /$slug -> $tenant_dir"
}

generate_landing_page() {
  local links="$1"
  cat > /usr/share/nginx/html/tenants/landing.html << EOF
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Decap CMS</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 480px; margin: 80px auto; padding: 0 24px; color: #1a1a1a; }
    h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 1.5rem; }
    ul { list-style: none; padding: 0; margin: 0; }
    li { border-bottom: 1px solid #eee; }
    li:first-child { border-top: 1px solid #eee; }
    a { display: block; padding: 12px 0; color: #2563eb; text-decoration: none; font-size: 1rem; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Decap CMS</h1>
  <ul>
$links
  </ul>
</body>
</html>
EOF
}

LINKS=""

if [ -f "$TENANTS_FILE" ]; then
  echo "Multi-tenant mode: loading $TENANTS_FILE"
  jq -e 'type == "array"' "$TENANTS_FILE" >/dev/null
  COUNT=$(jq 'length' "$TENANTS_FILE")

  if [ "$COUNT" -eq 0 ]; then
    echo "Tenants file must contain at least one tenant" >&2
    exit 1
  fi

  i=0
  while [ "$i" -lt "$COUNT" ]; do
    SLUG=$(jq -r ".[$i].slug" "$TENANTS_FILE")
    GITLAB_REPO=$(jq -r ".[$i].gitlabRepo" "$TENANTS_FILE")
    GITLAB_BRANCH=$(jq -r ".[$i].gitlabBranch" "$TENANTS_FILE")
    GITLAB_APP_ID=$(jq -r ".[$i].gitlabAppId" "$TENANTS_FILE")
    UPLOAD_URL=$(jq -r ".[$i].uploadUrl" "$TENANTS_FILE")
    PUBLISH_MODE=$(jq -r ".[$i].publishMode // \"simple\"" "$TENANTS_FILE")

    render_tenant "$SLUG" "$GITLAB_REPO" "$GITLAB_BRANCH" "$GITLAB_APP_ID" "$UPLOAD_URL" "$PUBLISH_MODE"
    LINKS="${LINKS}    <li><a href=\"/${SLUG}/\">${SLUG}</a></li>\n"
    i=$((i + 1))
  done

else
  echo "Single-tenant mode: using environment variables"
  SLUG="${DECAP_SLUG:-default}"
  render_tenant "$SLUG" "$GITLAB_REPO" "$GITLAB_BRANCH" "$GITLAB_APP_ID" "$UPLOAD_URL" "${PUBLISH_MODE:-simple}"
  LINKS="    <li><a href=\"/${SLUG}/\">${SLUG}</a></li>"
fi

generate_landing_page "$(printf '%b' "$LINKS")"
echo "  landing page: /"

exec "$@"
