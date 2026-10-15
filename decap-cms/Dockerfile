FROM nginx:1.31.7-alpine@sha256:42c36dfd0b3503b7966771550a91521262b4750665929821abf5069715610e20

RUN apk add --no-cache gettext jq

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
COPY config.yml.template /etc/decap/config.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
