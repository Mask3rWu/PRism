# PRism

## Environment

- Conda environment: `prism-py311`
- Activate with: `conda activate prism-py311`

## Project Structure

Frontend and backend are separated:

- Frontend: `/web`
- Backend: `/backend`

```
backend/
├─ api/                     # FastAPI routes
├─ core/                    # Config, LLM client, logging
├─ services/
│   ├─ github/              # GitHub API 封装 (fetch, auth, pagination)
│   └─ review/              # 入口：调用 graph，出口：后处理结果 (评分加权, 去重, 格式化)
├─ agents/                  # LangGraph graph
│   ├─ xxx_graph.py      # Graph DAG 声明 (nodes + edges)
│   ├─ states.py            # State schema
│   ├─ nodes/               # Node 实现 (fetch_pr, parse_diff, security, performance...)
│   └─ prompts/             # Prompt templates (.md)
├─ schemas/                 # Pydantic models
└─ main.py
```

Call chain: `api/ → services/review/ → agents/xxx_graph → agents/nodes/`

## Configuration

后端环境配置：`/backend/.env`，包含项目端口、LLM 配置（API keys、模型名称、endpoints 等）。

## Frontend Development

Use the `UI/UX Pro Max` skill for all frontend development work.
