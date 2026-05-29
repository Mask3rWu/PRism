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

## PR 规范

每个 PR 只做一件事：只实现或修改单一功能，粒度尽可能小。大功能应拆分为多个独立 PR 分步提交。

PR 标题与描述需清晰完整，内容包含：

- **标题**：一句话说明本 PR 新增/修改了什么。
- **功能描述**：说明该功能的作用与使用方式。
- **实现思路**：简要说明技术选型或核心实现逻辑。
- **测试方式**：如何验证该功能正常运行。

PR 合并后，主分支代码需保持可运行状态，评委在任意时间查看应能复现演示效果。

### PR 自动化流程

使用 GitHub CLI (`gh`) 进行 PR 的创建、合并和分支清理，无需浏览器操作。

**创建 PR：**
```bash
gh pr create --base main --head <feature-branch> \
  --title "feat: <简短描述>" \
  --body "## 功能描述

...

## 实现思路

...

## 测试方式

..."
```

**合并 PR（Squash & Merge）并删除远程分支：**
```bash
gh pr merge <PR-NUMBER> --merge --delete-branch
```

**合并后同步本地：**
```bash
git checkout main && git pull origin main
```

完整流程：`feature 分支开发 → push → gh pr create → gh pr merge → git pull origin main`。

## Frontend Development

Use the `UI/UX Pro Max` skill for all frontend development work.
