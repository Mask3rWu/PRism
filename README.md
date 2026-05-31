# PRism

AI 驱动的 PR 代码审查工具。

## 项目结构

```
PRism/
├── backend/          # FastAPI 后端
│   ├── api/          # API 路由
│   ├── agents/       # LangGraph 审查 Agent
│   ├── services/     # GitHub API 封装、审查服务
│   ├── schemas/      # Pydantic 模型
│   └── .env          # 环境配置（需手动创建）
└── web/              # Next.js 前端
```

## 环境要求

- **Python 3.11** + Conda
- **Node.js 20+**

## 依赖安装

### 后端

```bash
conda create -n prism-py311 python=3.11 -y
conda activate prism-py311
pip install -r backend/requirements.txt
```

### 前端

```bash
cd web
npm install
```

## 配置

复制并编辑后端环境配置文件：

```bash
cp backend/.env.example backend/.env
```

在 `.env` 中填入 LLM API Key 等必要配置。

## 启动

以下命令均在项目根目录执行。

### 后端（端口 8000）

```bash
conda activate prism-py311
uvicorn backend.main:app --reload --port 8000
```

### 前端（端口 3000）

```bash
cd web
npm run dev
```

启动后访问 `http://localhost:3000` 即可使用。

## MCP 集成（Claude Code）

在 Claude Code 中通过 MCP 直接查看 PR 审查结果，辅助代码修改。

### 注册 MCP Server

首先找到 conda 环境中 Python 的完整路径：

```bash
conda run -n prism-py311 which python
# 输出示例: /home/user/anaconda3/envs/prism-py311/bin/python
```

然后用 `claude mcp add` 注册（将 `<python-path>` 替换为上一步的输出）：

```bash
claude mcp add prism -- <python-path> -m backend.mcp.server
```

### 使用方式

在项目根目录打开 Claude Code，直接对话即可：

- **查看当前项目 PR 列表**：`列出当前项目的 PR`
- **查看 Review 结果**：`查看 PR #28 的 review 结果`
- **查看项目详情**：`当前是哪个项目`

Claude Code 会自动解析 git remote、匹配 PRism 项目、调用对应工具。

### 可用工具

| 工具 | 说明 |
|------|------|
| `get_current_project` | 通过 git remote 自动识别当前项目 |
| `list_projects` | 列出所有项目，支持搜索/标签/收藏筛选 |
| `get_project` | 获取项目详情（project_id 可选，自动检测） |
| `list_pull_requests` | 列出 PR，包含 review_id（project_id 可选） |
| `get_review_detail` | 获取完整 Review 结果（总结/风险/问题/测试） |

> **注意：** 使用前需确保 PRism 后端在 8000 端口运行。后端地址可通过环境变量 `PRISM_BACKEND_URL` 自定义。
