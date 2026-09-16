FROM nginx:1.31.6-alpine@sha256:092a82dc1cb2fa653ee660f24a8f8603f55b4ea9316923f9a0d394e50714ae10

RUN apk add --no-cache gettext jq

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
COPY config.yml.template /etc/decap/config.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
