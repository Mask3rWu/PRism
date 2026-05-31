# PRism

AI 驱动的 PR 代码审查工具。连接 GitHub 仓库，自动分析 Pull Request 的代码变更，生成多维度审查报告，并通过 MCP 协议集成到 Claude Code 中，实现 AI 辅助的代码审查闭环。

**演示视频：** [PRism 功能演示](https://space.bilibili.com/3546848040061812)

## 核心功能

- **PR 代码审查**：基于 LangGraph 多 Agent 协作，对 PR 进行代码总结、风险分析、问题检测、测试建议等多维度审查
- **GitHub 集成**：支持直接在平台上关联 GitHub 仓库，浏览 PR 列表，一键触发审查并查看结果
- **MCP Server**：通过 MCP 协议对接 Claude Code，在编码时直接调用 PRism 获取审查结果，实现"审查 → 修改"无缝闭环
- **Web 管理面板**：Next.js 前端提供项目管理、PR 列表、审查结果可视化

## 项目结构

```
PRism/
├── backend/              # FastAPI 后端
│   ├── api/              # API 路由
│   ├── agents/           # LangGraph 审查 Agent
│   │   ├── nodes/        # 审查节点（总结、风险、问题、测试）
│   │   └── prompts/      # Prompt 模板
│   ├── mcp/              # MCP Server
│   ├── services/         # GitHub API 封装、审查服务
│   └── schemas/          # Pydantic 模型
└── web/                  # Next.js 前端
```

## 环境要求

- **Python 3.11** + Conda
- **Node.js 20+**

## 快速开始

### 1. 安装依赖

```bash
# 后端
conda create -n prism-py311 python=3.11 -y
conda activate prism-py311
pip install -r backend/requirements.txt

# 前端
cd web && npm install
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

在 `.env` 中填入 LLM API Key、GitHub Token 等配置。

### 3. 启动服务

以下命令均在项目根目录执行。

```bash
# 后端（端口 8000）
conda activate prism-py311
uvicorn backend.main:app --reload --port 8000

# 前端（端口 3000）
cd web && npm run dev
```

启动后访问 `http://localhost:3000` 即可使用 Web 管理面板。

## MCP 集成（Claude Code）

在 Claude Code 中直接获取 PR 审查结果，边看审查意见边改代码。

### 注册 MCP Server

```bash
# 获取 conda 环境中的 Python 路径
conda run -n prism-py311 which python

# 注册 MCP Server（将 <python-path> 替换为上一步输出）
claude mcp add prism -- <python-path> -m backend.mcp.server
```

### 使用方式

在项目根目录打开 Claude Code，自然对话即可：

- **查看 PR 列表**：`列出当前项目的 PR`
- **查看审查结果**：`查看 PR #28 的 review 结果`
- **查看项目详情**：`当前是哪个项目`

Claude Code 会自动解析 git remote、匹配 PRism 项目、调用对应工具。

### 可用工具

| 工具 | 说明 |
|------|------|
| `get_current_project` | 通过 git remote 自动识别当前项目 |
| `list_projects` | 列出所有项目，支持搜索/标签/收藏筛选 |
| `get_project` | 获取项目详情（自动检测当前项目） |
| `list_pull_requests` | 列出 PR 列表，含 review_id |
| `get_review_detail` | 获取完整审查结果（总结/风险/问题/测试） |

> 使用前需确保 PRism 后端在 8000 端口运行。后端地址可通过环境变量 `PRISM_BACKEND_URL` 自定义。

## 待改进

- **审查 Agent 精细化**：当前多 Agent 协作的 prompt 策略仍有优化空间，不同维度的审查质量和一致性需要进一步提升
- **增量审查**：目前每次审查都重新分析全部 diff，未利用历史审查结果做增量对比，重复 PR 更新时效率较低
- **审查结果写回**：支持将审查结果以 PR Comment 形式自动写回 GitHub，目前写回策略和格式需要更灵活的配置
- **MCP 工具丰富**：当前 MCP 工具以查询为主，后续可增加触发审查、配置项目等写入类工具，减少切换 Web 面板的频率
- **测试覆盖**：后端核心审查流程和 MCP Server 缺乏自动化测试，长期维护风险较高
