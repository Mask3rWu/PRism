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
