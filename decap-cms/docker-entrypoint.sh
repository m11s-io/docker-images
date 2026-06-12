#!/bin/sh
set -e

envsubst '${GITLAB_REPO} ${GITLAB_BRANCH} ${GITLAB_APP_ID} ${UPLOAD_URL}' \
  < /etc/decap/config.yml.template \
  > /usr/share/nginx/html/admin/config.yml

exec "$@"
