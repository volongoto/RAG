<<<<<<< README.md

## 平台简介

RuoYi-Vue3-FastAPI是一套全部开源的快速开发平台，毫无保留给个人及企业免费使用。
* 前端采用Vue3、Element Plus，基于<u>[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)</u>前端项目修改。
* 后端采用FastAPI、sqlalchemy、PostgreSQL、Redis、OAuth2 & Jwt。
* 权限认证使用OAuth2 & Jwt，支持多终端认证系统。
* 支持加载动态权限菜单，多方式轻松权限控制。

## 代码结构

### 前端目录结构

```
ruoyi-fastapi-frontend/
├── bin/                    # 构建脚本
├── public/                  # 静态资源
├── src/
│   ├── api/               # API 接口
│   ├── assets/            # 静态资源
│   ├── components/        # 公共组件
│   ├── directive/         # 自定义指令
│   ├── layout/           # 布局组件
│   ├── plugins/           # 插件
│   ├── router/            # 路由配置
│   ├── store/             # 状态管理
│   ├── utils/             # 工具函数
│   ├── views/             # 页面视图
│   ├── App.vue           # 根组件
│   └── main.js           # 入口文件
├── vite/                 # Vite 配置
├── package.json           # 依赖配置
└── vite.config.js        # Vite 配置
```

### 后端目录结构

```
ruoyi-fastapi-backend/
├── alembic/              # 数据库迁移
├── common/                # 公共模块
│   ├── annotation/       # 注解
│   ├── aspect/           # 切面
│   ├── constant.py       # 常量
│   ├── context.py        # 上下文
│   ├── enums.py         # 枚举
│   ├── router.py         # 路由
│   └── vo.py            # 视图对象
├── config/                # 配置模块
│   ├── database.py       # 数据库配置
│   ├── env.py           # 环境配置
│   ├── get_db.py        # 数据库连接
│   ├── get_redis.py     # Redis 连接
│   └── get_scheduler.py  # 定时任务配置
├── exceptions/            # 异常处理
├── middlewares/           # 中间件
├── module_admin/          # 管理模块
│   ├── controller/       # 控制器
│   ├── dao/             # 数据访问层
│   ├── entity/           # 实体类
│   │   ├── do/         # 数据对象
│   │   └── vo/         # 视图对象
│   └── service/         # 服务层
├── module_generator/      # 代码生成模块
├── module_task/           # 定时任务模块
├── sql/                  # SQL 脚本
├── sub_applications/      # 子应用
├── utils/                # 工具类
├── app.py                # 应用入口
├── server.py             # 服务器启动
├── requirements.txt       # 依赖列表
└── Dockerfile            # Docker 配置
```

## 后端技术选型

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 核心框架 | FastAPI | 0.125.0 | 现代化的 Python Web 框架 |
| ORM | SQLAlchemy | 2.0.45 | Python SQL 工具包和对象关系映射 |
| 数据库驱动 | asyncpg | 0.31.0 | PostgreSQL 异步驱动 |
| 数据库驱动 | psycopg2 | 2.9.11 | PostgreSQL 数据库适配器 |
| 缓存 | redis | 6.4.0 | Redis 客户端 |
| 任务调度 | APScheduler | 3.11.1 | Python 定时任务库 |
| 数据库迁移 | Alembic | 1.16.5 | 数据库迁移工具 |
| 认证 | PyJWT | 2.10.1 | JWT 令牌生成和验证 |
| 密码加密 | bcrypt | 5.0.0 | 密码哈希库 |
| 数据处理 | pandas | 2.3.3 | 数据分析和处理 |
| 数据处理 | openpyxl | 3.1.5 | Excel 文件读写 |
| 日志 | loguru | 0.7.3 | Python 日志库 |
| 文件处理 | aiofiles | 25.1.0 | 异步文件操作 |
| 缓存 | async-lru | 2.0.5 | LRU 缓存实现 |
| 用户代理 | user-agents | 2.2.0 | 浏览器用户代理解析 |
| SQL 解析 | sqlglot | 28.5.0 | SQL 解析和转换 |
| 代码质量 | ruff | 0.14.10 | Python 代码检查和格式化 |
| 数据验证 | pydantic-validation-decorator | 0.1.5 | Pydantic 验证装饰器 |
| 图像处理 | Pillow | 11.3.0 | Python 图像处理库 |
| 系统信息 | psutil | 7.1.3 | 系统和进程工具 |

## 前端技术选型

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Vue | 3.5.16 | 渐进式 JavaScript 框架 |
| UI 组件 | Element Plus | 2.10.7 | Vue 3 组件库 |
| UI 组件 | Ant Design Vue | 4.1.1 | 企业级 UI 设计语言 |
| 路由 | Vue Router | 4.5.1 | Vue.js 官方路由 |
| 状态管理 | Pinia | 3.0.2 | Vue 状态管理库 |
| 构建工具 | Vite | 6.3.5 | 下一代前端构建工具 |
| HTTP 客户端 | Axios | 1.9.0 | 基于 Promise 的 HTTP 客户端 |
| 图表 | ECharts | 5.6.0 | 数据可视化图表库 |
| 图表 | @antv/g2plot | 2.4.31 | 可视化图表库 |
| 富文本编辑器 | @vueup/vue-quill | 1.2.0 | Vue 3 Quill 编辑器 |
| 图片裁剪 | vue-cropper | 1.1.1 | Vue 图片裁剪组件 |
| 拖拽 | vuedraggable | 4.1.0 | Vue 拖拽组件 |
| 工具库 | js-cookie | 3.0.5 | Cookie 操作 |
| 工具库 | JSEncrypt | 3.3.2 | JavaScript 加密库 |
| 工具库 | clipboard | 2.0.11 | 剪贴板操作 |
| 工具库 | file-saver | 2.0.5 | 文件保存 |
| 工具库 | fuse.js | 6.6.2 | 模糊搜索库 |
| 工具库 | splitpanes | 4.0.4 | 可调整大小的分割窗格 |
| 工具库 | nprogress | 0.2.0 | 进度条 |
| 图标 | @ant-design/icons-vue | 7.0.1 | Ant Design 图标库 |
| 图标 | @element-plus/icons-vue | 2.3.1 | Element Plus 图标库 |
| 开发工具 | Less | 4.2.0 | CSS 预处理器 |
| 开发工具 | Sass | 1.89.1 | CSS 预处理器 |
| 开发工具 | unplugin-auto-import | 0.18.6 | 自动导入插件 |
| 开发工具 | unplugin-vue-setup-extend-plus | 1.0.1 | Vue Setup 语法支持 |
| 开发工具 | vite-plugin-compression | 0.5.1 | Gzip 压缩插件 |
| 开发工具 | vite-plugin-svg-icons | 2.0.1 | SVG 图标插件 |

## 数据库

| 数据库 | 版本 | 说明 |
|------|------|------|
| PostgreSQL | 17.2 | 开源对象关系数据库系统 |
| Redis | latest | 内存数据结构存储 |

## Python 版本

| 项目 | 版本 | 说明 |
|------|------|------|
| Python | 3.12 | Python 编程语言 |

## 内置功能

1. 用户管理：用户是系统操作者，该功能主要完成系统用户配置。
2. 角色管理：角色菜单权限分配、设置角色按机构进行数据范围权限划分。
3. 菜单管理：配置系统菜单，操作权限，按钮权限标识等。
4. 部门管理：配置系统组织机构（公司、部门、小组）。
5. 岗位管理：配置系统用户所属担任职务。
6. 字典管理：对系统中经常使用的一些较为固定的数据进行维护。
7. 参数管理：对系统动态配置常用参数。
8. 通知公告：系统通知公告信息发布维护。
9. 操作日志：系统正常操作日志记录和查询；系统异常信息日志记录和查询。
10. 登录日志：系统登录日志记录查询包含登录异常。
11. 在线用户：当前系统中活跃用户状态监控。
12. 定时任务：在线（添加、修改、删除）任务调度包含执行结果日志。
13. 服务监控：监视当前系统CPU、内存、磁盘、堆栈等相关信息。
14. 缓存监控：对系统的缓存信息查询，命令统计等。
15. 在线构建器：拖动表单元素生成相应的HTML代码。
16. 系统接口：根据业务代码自动生成相关的api接口文档。
17. 代码生成：配置数据库表信息一键生成前后端代码（python、sql、vue、js），支持下载。

## 项目开发及发布相关

### 开发

```bash
# 克隆项目
git clone https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI.git

# 进入项目根目录
cd RuoYi-Vue3-FastAPI
```

#### 前端

```bash
# 进入前端目录
cd ruoyi-fastapi-frontend

# 安装依赖
npm install 或 yarn --registry=https://registry.npmmirror.com

# 建议不要直接使用 cnpm 安装依赖，会有各种诡异的 bug。可以通过如下操作解决 npm 下载速度慢的问题
npm install --registry=https://registry.npmmirror.com

# 启动服务
npm run dev 或 yarn dev
```

#### 后端

```bash
# 进入后端目录
cd ruoyi-fastapi-backend

# 安装项目依赖环境
pip3 install -r requirements.txt

# 配置环境
在.env.dev文件中配置开发环境的数据库和redis

# 运行sql文件
1.新建数据库ruoyi-fastapi(默认，可修改)
2.使用命令或数据库连接工具运行sql文件夹下的ruoyi-fastapi-pg.sql

# 运行后端
python3 app.py --env=dev
```

#### 访问

```bash
# 默认账号密码
账号：admin
密码：admin123

# 浏览器访问
地址：http://localhost:80
```

### 发布

#### 前端

```bash
# 构建测试环境
npm run build:stage 或 yarn build:stage

# 构建生产环境
npm run build:prod 或 yarn build:prod
```

#### 后端

```bash
# 配置环境
在.env.prod文件中配置生产环境的数据库和redis

# 运行后端
python3 app.py --env=prod
```

### Docker Compose部署方式

> ⚠️ **警告：** 默认未做数据持久化配置，请注意数据备份或自行配置持久化

```bash
docker compose up -d --build
```

