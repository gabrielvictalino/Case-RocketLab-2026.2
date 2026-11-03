# syntax=docker/dockerfile:1
FROM node:24-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./

RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -s /run/secrets/proxy_ca ]; then \
        export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; \
        export NPM_CONFIG_CAFILE=/run/secrets/proxy_ca; \
    fi \
    && npm ci

COPY frontend/ ./

RUN npm run build

FROM nginx:1.28-alpine

RUN rm -f /etc/nginx/conf.d/default.conf

COPY infra/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
