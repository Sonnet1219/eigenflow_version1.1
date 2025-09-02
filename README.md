# LLM-FRAME Quick Start

一个基于 **LangGraph** + **Supabase** + **FastAPI** 的快速启动模板，帮助开发者快速上手智能对话应用开发。

## ✨ 项目特性

- 🚀 **LangGraph 工作流**：最简单的聊天流程实现，展示状态管理和图构建
- 💾 **PostgreSQL 持久化**：集成 LangGraph checkpoint 机制，支持会话状态保存
- 🧠 **长期记忆存储**：基于 AsyncPostgresStore 的持久化记忆管理
- ⚡ **全异步架构**：从数据库连接到 API 接口的完整异步实现
- 🔄 **FastAPI 后端**：包含 lifespan 管理、异常处理和 CORS 配置
- 🗄️ **Supabase 集成**：本地 Docker 部署支持，包含完整的数据库管理
- 📊 **可视化开发**：支持 LangGraph 可视化调试和流程预览
- 🛠️ **标准项目结构**：清晰的模块化代码组织

## 📁 项目结构

```
./
├── src/
│   ├── agent/          # LangGraph 智能体核心逻辑
│   │   ├── graph.py    # 工作流图定义
│   │   ├── state.py    # 状态管理
│   │   └── configuration.py  # 配置管理
│   ├── api/            # FastAPI 接口层
│   │   ├── app.py      # 应用主程序
│   │   └── graph.py    # 图相关路由
│   └── db/             # 数据库管理 (全异步架构)
│       ├── database.py # 异步数据库连接池
│       ├── checkpoints.py  # 会话状态检查点管理
│       └── memory_store.py # 长期记忆存储管理
├── resource/           # 资源文件
└── tests/             # 测试用例
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install .
```

### 2. 环境配置

复制 `.env.example` 为 `.env` 并配置必要参数：

```bash
cp .env.example .env
```

**必填配置项：**
```env
# LangSmith 可观测性 (可选)
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=eigenflow

# 大模型 API Key (阿里云DashScope示例)
DASHSCOPE_API_KEY=your_dashscope_key

# 数据库连接
DATABASE_URL="postgresql://user:password@host:port/database"

# Supabase 设置 (本地部署)
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=your_anon_key
```

### 3. 启动服务

```bash
python -m src.main
```

- 🌐 API 服务：`http://localhost:8001`
- 📖 API 文档：`http://localhost:8001/docs`

### 4. 开发模式 (可选)

启用 LangGraph 可视化开发：
```bash
langgraph dev
```

## 🤖 核心功能

### 最简聊天工作流

项目实现了一个基础的聊天流程：

```python
# 工作流: START -> chat -> END
builder = StateGraph(OverallState, config_schema=Configuration)
builder.add_node("chat", chat_node)
builder.add_edge(START, "chat")
builder.add_edge("chat", END)
```

### API 调用示例

```bash
curl -X POST "http://localhost:8001/agent/chat" \
     -H "Content-Type: application/json" \
     -d '{"text": "你好!", "thread_id": "user-123"}'
```

## 📚 相关资源

### Supabase 本地部署
- 📋 [本地 Docker 部署指南](resource/supabase_docker_guide.md)
- 📖 [Supabase Python 客户端文档](https://supabase.com/docs/reference/python/start)

### LangGraph 学习资源  
- 🎯 [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- 🚀 快速入门和进阶教程，掌握状态工作流构建

---

本项目为开发者提供一个生产就绪的起点，集成了现代 AI 应用开发的核心组件。

