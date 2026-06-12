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
  envsubst '${GITLAB_REPO} ${GITLAB_BRANCH} ${GITLAB_APP_ID} ${UPLOAD_URL}' \
    < "$CONFIG_TEMPLATE" > "$tenant_dir/config.yml"

  echo "  configured: /$slug -> $tenant_dir"
}

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

    render_tenant "$SLUG" "$GITLAB_REPO" "$GITLAB_BRANCH" "$GITLAB_APP_ID" "$UPLOAD_URL"
    i=$((i + 1))
  done

else
  echo "Single-tenant mode: using environment variables"
  render_tenant "${DECAP_SLUG:-default}" "$GITLAB_REPO" "$GITLAB_BRANCH" "$GITLAB_APP_ID" "$UPLOAD_URL"
fi

exec "$@"
