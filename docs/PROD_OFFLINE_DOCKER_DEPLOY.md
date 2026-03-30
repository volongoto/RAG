# 生产环境离线 Docker 部署说明

本文档用于通过离线 Docker 镜像包交付并部署 `Cradle` 全套服务。

适用前提：

- 目标环境为 Linux
- Docker Engine 24+
- Docker Compose Plugin 2.20+
- 生产服务器规格：内存 256G，磁盘 1T SSD/NVMe
- RAG 场景：约 10 万级文档入库，向量存储使用 PostgreSQL 17 + pgvector

## 1. 新增文件

- 生产编排文件：`docker-compose-prod.yml`
- PostgreSQL 生产配置：`deploy/postgres/postgresql.prod.conf`
- 前端生产代理配置：`ruoyi-fastapi-frontend/bin/nginx.prod.conf`
- 生产部署文档：`docs/PROD_OFFLINE_DOCKER_DEPLOY.md`

## 2. 推荐部署目录

建议把整个项目放在固定目录，例如：

```bash
/opt/cradle
```

后文所有 `./xxx` 相对路径，都是相对于 `/opt/cradle` 这个部署根目录。

## 3. 配置文件和数据目录放置位置

如果部署根目录是 `/opt/cradle`，则各配置和数据目录的实际位置如下。

| 用途                   | 宿主机路径                                                        | 容器内路径                                                 | 说明                       |
| -------------------- | ------------------------------------------------------------ | ----------------------------------------------------- | ------------------------ |
| 生产编排文件               | `/opt/cradle/docker-compose-prod.yml`                        | -                                                     | 生产环境启动入口                 |
| 后端生产环境变量             | `/opt/cradle/ruoyi-fastapi-backend/.env.prod`                | -                                                     | 后端 `env_file` 使用         |
| PostgreSQL 配置文件      | `/opt/cradle/deploy/postgres/postgresql.prod.conf`           | `/etc/postgresql/postgresql.conf`                     | PostgreSQL 和 pgvector 参数 |
| PostgreSQL 数据目录      | `/opt/cradle/data/cradle-db`                                 | `/var/lib/postgresql/data`                            | 持久化挂载根目录                 |
| PostgreSQL 实际 PGDATA | `/opt/cradle/data/cradle-db/pgdata`                          | `/var/lib/postgresql/data/pgdata`                     | 真正的库文件位置                 |
| PostgreSQL 初始化 SQL   | `/opt/cradle/ruoyi-fastapi-backend/sql/ruoyi-fastapi-pg.sql` | `/docker-entrypoint-initdb.d/1-cradle-fastapi-pg.sql` | 首次初始化执行                  |
| RAG 初始化 SQL          | `/opt/cradle/ruoyi-fastapi-backend/sql/rag_tables.sql`       | `/docker-entrypoint-initdb.d/2-rag_tables.sql`        | 首次初始化执行                  |
| 前端 Nginx 配置          | `/opt/cradle/ruoyi-fastapi-frontend/bin/nginx.prod.conf`     | `/etc/nginx/conf.d/default.conf`                      | 前端代理 `/prod-api`         |
| 后端上传目录               | `/opt/cradle/data/cradle-backend/upload_path`                | `/app/vf_admin/upload_path`                           | 上传文件持久化                  |
| 后端解析缓存目录             | `/opt/cradle/data/cradle-backend/download_path`              | `/app/vf_admin/download_path`                         | 文档解析临时文件                 |
| 后端日志目录               | `/opt/cradle/logs/cradle-backend`                            | `/app/logs`                                           | 后端运行日志                   |
| Redis 数据目录           | `/opt/cradle/data/cradle-redis`                              | `/data`                                               | Redis AOF 持久化            |
| MinIO 数据目录           | `/opt/cradle/data/cradle-minio`                              | `/data`                                               | 对象存储持久化                  |

### 3.1 PostgreSQL 库文件位置说明

PostgreSQL 的“库文件位置”分为三层：

1. 宿主机持久化目录：`/opt/cradle/data/cradle-db`
2. 容器挂载目录：`/var/lib/postgresql/data`
3. 容器实际 PGDATA：`/var/lib/postgresql/data/pgdata`

因此真正的 PostgreSQL 数据文件最终会出现在宿主机：

```bash
/opt/cradle/data/cradle-db/pgdata
```

这里会包含数据库文件、WAL、索引等内容。备份库文件目录时，备份这个宿主机目录即可。

## 4. 服务器目录准备

在目标服务器放置完整项目目录后，执行：

```bash
mkdir -p /opt/cradle/data/cradle-backend/upload_path
mkdir -p /opt/cradle/data/cradle-backend/download_path
mkdir -p /opt/cradle/data/cradle-db
mkdir -p /opt/cradle/data/cradle-redis
mkdir -p /opt/cradle/data/cradle-minio
mkdir -p /opt/cradle/logs/cradle-backend
cp /opt/cradle/ruoyi-fastapi-backend/.env.prod.example /opt/cradle/ruoyi-fastapi-backend/.env.prod
```

然后编辑：

```bash
/opt/cradle/ruoyi-fastapi-backend/.env.prod
```

至少确认以下参数：

- `DB_PASSWORD`
- `RAG_LLM_API_KEY`
- `RAG_EMBEDDING_API_KEY`
- `RAG_MINIO_ACCESS_KEY`
- `RAG_MINIO_SECRET_KEY`

同时手工修改：

```bash
/opt/cradle/docker-compose-prod.yml
```

注意：

- 把 `cradle-db.environment.POSTGRES_PASSWORD` 改成正式数据库密码。
- 把 `cradle-minio.environment.MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 改成正式 MinIO 凭据。
- `docker-compose-prod.yml` 里的 `POSTGRES_PASSWORD` 必须与 `/opt/cradle/ruoyi-fastapi-backend/.env.prod` 里的 `DB_PASSWORD` 保持一致。
- `docker-compose-prod.yml` 里的 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 必须与 `.env.prod` 里的 `RAG_MINIO_ACCESS_KEY` / `RAG_MINIO_SECRET_KEY` 保持一致。

## 5. x86\_64 版本离线镜像打包

以下操作建议在一台可联网的构建机完成。

### 5.1 构建业务镜像

前端生产镜像必须显式使用 `BUILD_MODE=prod`，否则会构建成 `/docker-api` 版本。

```bash
docker build -t cradle-frontend:prod --build-arg BUILD_MODE=prod ./ruoyi-fastapi-frontend
docker build -t cradle-backend:prod ./ruoyi-fastapi-backend
```

### 5.2 拉取基础镜像

```bash
docker pull pgvector/pgvector:pg17
docker pull redis:7.4-alpine
docker pull minio/minio:RELEASE.2025-02-28T09-55-16Z
```

### 5.3 导出离线镜像包

```bash
docker image save -o cradle-prod-images.tar \
  cradle-frontend:prod \
  cradle-backend:prod \
  pgvector/pgvector:pg17 \
  redis:7.4-alpine \
  minio/minio:RELEASE.2025-02-28T09-55-16Z
```

将以下内容一并传到生产服务器：

- `cradle-prod-images.tar`
- 整个项目目录 `/opt/cradle`

## 6. ARM64 版本离线镜像打包

如果目标服务器是 ARM64，例如鲲鹏、飞腾、Ampere、ARM 云主机等，建议使用 `docker buildx` 构建 `linux/arm64` 镜像。

### 6.1 初始化 buildx

首次使用时执行：

```bash
docker buildx create --name cradle-multiarch --use
docker buildx inspect --bootstrap
```

如果构建机本身不是 ARM64，而是 x86\_64，需要先启用 QEMU：

```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

### 6.2 构建 ARM64 业务镜像

```bash
docker buildx build --platform linux/arm64 -t cradle-frontend:prod-arm64 --build-arg BUILD_MODE=prod --load ./ruoyi-fastapi-frontend
docker buildx build --platform linux/arm64 -t cradle-backend:prod-arm64 --load ./ruoyi-fastapi-backend
```

### 6.3 拉取 ARM64 基础镜像

```bash
docker pull --platform linux/arm64 pgvector/pgvector:pg17
docker pull --platform linux/arm64 redis:7.4-alpine
docker pull --platform linux/arm64 minio/minio:RELEASE.2025-02-28T09-55-16Z
```

### 6.4 导出 ARM64 离线镜像包

```bash
docker  save -o cradle-prod-images-arm64.tar \
  cradle-frontend:prod-arm64 \
  cradle-backend:prod-arm64 \
  pgvector/pgvector:pg17 \
  redis:7.4-alpine \
  minio/minio:RELEASE.2025-02-28T09-55-16Z
```

### 6.5 ARM64 镜像校验

```bash
docker  inspect cradle-frontend:prod-arm64 --format '{{.Architecture}}'
docker image inspect cradle-backend:prod-arm64 --format '{{.Architecture}}'
```

期望输出：

```bash
arm64
```

### 6.6 ARM64 生产环境启动方式

如果生产环境使用同一份 `docker-compose-prod.yml`，不要通过环境变量切换镜像，直接手工修改 YAML：

```bash
image: cradle-frontend:prod-arm64
image: cradle-backend:prod-arm64
```

修改完 `docker-compose-prod.yml` 后再启动：

```bash
cd /opt/cradle
docker compose -f docker-compose-prod.yml up -d
```

## 7. 生产服务器导入离线镜像

### 7.1 x86\_64

```bash
docker load -i cradle-prod-images.tar
docker image ls | grep -E 'cradle-|pgvector|redis|minio'
```

### 7.2 ARM64

```bash
docker load -i cradle-prod-images-arm64.tar
docker image ls | grep -E 'cradle-|pgvector|redis|minio'
```

## 8. 启动生产环境

先检查 Compose 结果：

```bash
cd /opt/cradle
docker compose -f docker-compose-prod.yml config > /tmp/cradle-compose-check.yaml
```

确认无误后启动：

```bash
cd /opt/cradle
docker compose -f docker-compose-prod.yml up -d
```

查看状态：

```bash
cd /opt/cradle
docker compose -f docker-compose-prod.yml ps
docker compose -f docker-compose-prod.yml logs -f cradle-db
docker compose -f docker-compose-prod.yml logs -f cradle-backend
```

## 9. 访问地址

- 前端入口：`http://<server-ip>:18080`
- 后端 API：`http://127.0.0.1:29099/prod-api`
- MinIO API：`http://127.0.0.1:19000`
- MinIO Console：`http://127.0.0.1:19001`
- PostgreSQL：`127.0.0.1:54322`
- Redis：`127.0.0.1:26379`

说明：

- PostgreSQL、Redis、MinIO、后端 API 默认仅绑定宿主机 `127.0.0.1`。
- 如需远程运维访问，建议通过堡垒机、SSH 隧道或安全组白名单控制，不建议直接改成 `0.0.0.0`。

## 10. pgvector 生产参数说明

生产版 PostgreSQL 使用文件：

```bash
/opt/cradle/deploy/postgres/postgresql.prod.conf
```

重点参数如下：

- `shared_buffers=64GB`
- `effective_cache_size=192GB`
- `maintenance_work_mem=8GB`
- `autovacuum_work_mem=2GB`
- `ivfflat.probes=20`
- `max_wal_size=32GB`
- `wal_compression=on`
- `shm_size=72gb`
- `POSTGRES_INITDB_ARGS` 中启用了 `--data-checksums`

这些参数是按 256G 内存、1T SSD、10 万级文档向量化后的检索场景配置的。

## 11. 向量索引策略

初始化 SQL 已将 `rag_chunk` 的向量索引调整为：

- `IVFFlat`
- `lists = 1000`
- 仅索引 `del_flag = '0'` 的有效数据

如果你的生产数据库已经初始化过，`docker-entrypoint-initdb.d` 不会再次执行，需要手工重建索引：

```sql
DROP INDEX IF EXISTS idx_chunk_embedding;
CREATE INDEX CONCURRENTLY idx_chunk_embedding
ON rag_chunk
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000)
WHERE del_flag = '0';

ANALYZE rag_chunk;
```

建议在业务低峰期执行。

## 12. 首次初始化检查项

首次启动后建议检查：

```bash
docker exec -it cradle-db psql -U postgres -p 54322 -d cradle-fastapi -c "SELECT extname FROM pg_extension;"
docker exec -it cradle-db psql -U postgres -p 54322 -d cradle-fastapi -c "\\d+ rag_chunk"
docker exec -it cradle-db psql -U postgres -p 54322 -d cradle-fastapi -c "\\di+ idx_chunk_embedding"
docker exec -it cradle-redis redis-cli ping
```

期望结果：

- PostgreSQL 中存在 `vector` 扩展
- `rag_chunk.embedding` 字段为 `vector(1024)`
- `idx_chunk_embedding` 已创建
- Redis 返回 `PONG`

## 13. 备份建议

### 13.1 PostgreSQL

```bash
pg_dump -h 127.0.0.1 -p 54322 -U postgres -Fc cradle-fastapi > cradle-fastapi-$(date +%F).dump
```

### 13.2 目录级备份

建议同时备份以下目录和文件：

- `/opt/cradle/data/cradle-db`
- `/opt/cradle/data/cradle-minio`
- `/opt/cradle/data/cradle-redis`
- `/opt/cradle/ruoyi-fastapi-backend/.env.prod`

## 14. 常见注意事项

### 14.1 前端 API 前缀必须与生产环境一致

生产前端镜像必须使用：

```bash
docker build -t cradle-frontend:prod --build-arg BUILD_MODE=prod ./ruoyi-fastapi-frontend
```

否则前端会继续请求 `/docker-api`，与生产版 `APP_ROOT_PATH=/prod-api` 不一致。

### 14.2 Swagger/ReDoc 在纯离线网络下可能无法完全加载

当前后端文档静态资源默认引用外部 CDN。业务接口不受影响，但如果生产网络完全隔离，Swagger/ReDoc 页面可能无法正常渲染。若需要完全内网化，需要进一步把这些静态资源内置到镜像中。

### 14.3 文档规模继续增长时的建议

当 `rag_chunk` 达到数百万以上时，建议进一步评估：

- 按知识库或时间对 `rag_chunk` 分区
- 将 `lists` 提升到 `sqrt(row_count)` 量级重新建索引
- 将冷数据迁移到归档库
- 结合业务压测调整 `ivfflat.probes`

