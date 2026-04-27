ARG NODE_BASE_IMAGE=node:18-slim
ARG NGINX_BASE_IMAGE=nginx:latest

FROM ${NODE_BASE_IMAGE} AS builder

WORKDIR /app

ARG BUILD_MODE=docker

COPY package*.json ./
RUN npm config set registry https://registry.npmmirror.com
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN case "$BUILD_MODE" in \
    docker) npm run build:docker ;; \
    prod|production) npm run build:prod ;; \
    stage|staging) npm run build:stage ;; \
    *) echo "Unsupported BUILD_MODE: $BUILD_MODE" >&2; exit 1 ;; \
    esac

FROM ${NGINX_BASE_IMAGE}

WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
