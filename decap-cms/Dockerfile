FROM nginx:1.31.6-alpine@sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2

RUN apk add --no-cache gettext jq

COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
COPY config.yml.template /etc/decap/config.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
