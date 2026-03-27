FROM node:18-slim AS builder

WORKDIR /app

ARG BUILD_MODE=docker

COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com
RUN npm ci

COPY . .
RUN case "$BUILD_MODE" in \
    docker) npm run build:docker ;; \
    prod|production) npm run build:prod ;; \
    stage|staging) npm run build:stage ;; \
    *) echo "Unsupported BUILD_MODE: $BUILD_MODE" >&2; exit 1 ;; \
    esac

FROM nginx:latest

WORKDIR /usr/share/nginx/html

COPY --from=builder /app/dist ./

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
