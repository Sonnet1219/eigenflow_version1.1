# EigenFlow Multi-Agent Quick Start

基于 **LangGraph** + **Supabase** + **FastAPI** 构建的生产级多智能体系统，专注于智能金融风险分析和投资组合管理对话。

## ✨ 项目特性 Project Features

- 🤖 **多智能体监督架构 Multi-Agent Supervisor Architecture**: 使用 LangGraph 预构建监督模式在聊天助手和保证金检查助手之间进行智能任务路由
- 📊 **实时金融数据 Real-Time Financial Data**: 直接集成 EigenFlow API，获取 LP 账户持仓、保证金报告和风险分析
- 🚀 **LangGraph 工作流 Advanced Workflow**: 使用 handoff tools 和状态管理实现高级多智能体协调
- 💾 **PostgreSQL 持久化 Persistence**: 集成 LangGraph checkpoint 机制，支持会话状态保存
- 🧠 **长期记忆存储 Long-Term Memory**: 基于 AsyncPostgresStore 的持久化记忆管理
- ⚡ **全异步架构 Full Async Architecture**: 从数据库连接到 API 接口的完整异步实现
- 🔄 **FastAPI 后端 Production Backend**: 包含 lifespan 管理、异常处理和 CORS 配置
- 🗄️ **Supabase 集成 Database Integration**: 本地 Docker 部署支持，包含完整的数据库管理
- 📊 **可视化开发 Visual Development**: 支持 LangGraph 可视化调试和流程预览
- 🛠️ **标准项目结构 Standard Structure**: 清晰的模块化代码组织，专为多智能体系统设计

## 📁 项目结构 Project Structure

```
./
├── src/
│   ├── agent/          # LangGraph 多智能体核心逻辑 Multi-agent core logic
│   │   ├── graph.py    # 工作流图定义 Workflow graph definition
│   │   ├── state.py    # 状态管理 State management
│   │   ├── mcp.py      # EigenFlow API 集成 API integration
│   │   ├── prompts.py  # 智能体提示词 Agent prompts
│   │   └── configuration.py  # 配置管理 Configuration
│   ├── api/            # FastAPI 接口层 API layer
│   │   ├── app.py      # 应用主程序 Main application
│   │   └── graph.py    # 图相关路由 Graph routes
│   └── db/             # 数据库管理 Database management (全异步架构)
│       ├── database.py # 异步数据库连接池 Async database pool
│       ├── checkpoints.py  # 会话状态检查点管理 Session checkpoints
│       └── memory_store.py # 长期记忆存储管理 Memory storage
├── resource/           # 资源文件 Resources
└── tests/             # 测试用例 Test cases
```

## 🚀 快速开始 Quick Start

### 1. 安装依赖 Install Dependencies

```bash
pip install .
```

### 2. 环境配置 Environment Setup

复制 `.env.example` 为 `.env` 并配置必要参数：

```bash
cp .env.example .env
```

**必填配置项 Required Configuration:**
```env
# LangSmith 可观测性 (可选) Observability (optional)
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=eigenflow

# 大模型 API Key Model API Key
DASHSCOPE_API_KEY=your_dashscope_key

# 数据库连接 Database Connection
DATABASE_URL="postgresql://user:password@host:port/database"

# EigenFlow API 配置 API Configuration
EIGENFLOW_EMAIL=your_email
EIGENFLOW_PASSWORD=your_password
EIGENFLOW_BROKER=your_broker

# Supabase 设置 (本地部署) Local deployment
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=your_anon_key
```

### 3. 启动服务 Start Services

```bash
python -m src.main
```

- 🌐 API 服务 API Service：`http://localhost:8001`
- 📖 API 文档 Documentation：`http://localhost:8001/docs`

### 4. 开发模式 Development Mode (可选)

启用 LangGraph 可视化开发：
```bash
langgraph dev
```

## 🤖 核心功能 Core Features

### 多智能体监督工作流 Multi-Agent Supervisor Workflow

项目实现了基于监督者模式的多智能体系统 The project implements a supervisor-based multi-agent system:

```python
# 使用 create_supervisor 构建多智能体系统
graph = create_supervisor(
    [chat_assistant, margin_assistant],
    model=model,
    prompt=SUPERVISOR_PROMPT,
    add_handoff_messages=False,  # 不将切换消息添加到对话历史 
    output_mode="last_message",   # 仅返回活跃智能体的最后消息
    tools=[forwarding_tool]       # 避免supervisor重写子agent query时的信息丢失和token浪费

给用户还可以保存一些令牌。between agents
)
```

### 智能体类型 Agent Types

1. **Chat Assistant 聊天助手**: 处理一般对话和问题
2. **Margin Assistant 保证金助手**: 处理 LP 保证金检查和风险分析

### API 调用示例 API Examples

```bash
curl -X POST "http://localhost:8001/agent/chat" \
     -H "Content-Type: application/json" \
     -d '{"text": "帮我查查lp的margin水平情况", "thread_id": "user-123", "model": "qwen-plus-latest"}'
```

## 📚 相关资源 Related Resources

### Supabase 本地部署
- 📋 [本地 Docker 部署指南](resource/supabase_docker_guide.md)
- 📖 [Supabase Python 客户端文档](https://supabase.com/docs/reference/python/start)

### LangGraph 学习资源 Learning Resources
- 🎯 [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- 🤖 [Multi-Agent Systems](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- 🔧 [LangGraph Supervisor](https://github.com/langchain-ai/langgraph-supervisor-py)

---

本项目为开发者提供一个生产就绪的多智能体金融分析系统起点，集成了现代 AI 应用开发的核心组件。

This project provides developers with a production-ready starting point for multi-agent financial analysis systems, integrating core components of modern AI application development.
