# NexusAgent - 智能代理系统

NexusAgent 是一个基于 LangGraph 和 FastAPI 构建的现代化智能代理系统，支持多模型集成、工具调用、人工审核、会话管理和长期记忆功能。

## 🚀 主要特性

- **多模型支持**: 集成通义千问(Qwen)、DeepSeek等主流大语言模型
- **智能工具调用**: 支持自定义工具和MCP服务器工具集成
- **人工审核机制**: 工具调用前的人工审核(Human-in-the-Loop)
- **会话管理**: 基于Redis的分布式会话状态管理
- **长期记忆**: 基于PostgreSQL的用户偏好和记忆存储
- **前端界面**: Rich库构建的交互式命令行界面
- **RESTful API**: 完整的后端API接口服务

## 📁 项目结构

```
NexusAgent/
├── configs/                    # 配置模块
│   ├── __init__.py
│   ├── configuration.py       # 主要配置类(数据库、Redis、API等)
│   ├── mcp_server.py          # MCP服务器配置
│   └── model_configs.py       # 模型配置参数
├── frontend/                   # 前端模块
│   └── frontend_main.py       # Rich库构建的交互式客户端
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── data_models.py         # Pydantic数据模型定义
│   ├── llms.py                # 大语言模型初始化和管理
│   ├── message_tools.py       # 消息处理和解析工具
│   ├── redis_manager.py       # Redis会话管理器
│   └── tools.py               # 工具定义和人工审核逻辑
├── logfile/                    # 日志文件目录
│   └── app.log                # 应用日志
├── markdown/                   # 文档目录
│   └── system_massage.md      # 系统提示词模板
├── main.py                     # 主应用程序入口
├── pyproject.toml             # 项目依赖配置
├── setup.py                   # 项目安装配置
└── uv.lock                    # 依赖锁定文件
```

## 🛠️ 技术栈

### 后端核心

- **FastAPI**: 现代化的Python Web框架
- **LangGraph**: 智能代理状态图管理
- **LangChain**: 大语言模型应用开发框架
- **PostgreSQL**: 关系型数据库(短期记忆和长期存储)
- **Redis**: 内存数据库(会话状态管理)

### 模型集成

- **通义千问(Qwen)**: 阿里云大语言模型
- **DeepSeek**: DeepSeek大语言模型
- **DashScope**: 阿里云模型服务平台

### 工具与服务

- **MCP (Model Context Protocol)**: 模型上下文协议
- **高德地图API**: 地理位置服务集成
- **Rich**: 终端界面美化库

## 📋 环境要求

- Python >= 3.13
- PostgreSQL >= 12
- Redis >= 6.0

### 重要版本说明

本项目使用了最新版本的LangChain和LangGraph框架：

- **LangChain >= 1.0.3** (2025年10月26日发布)
- **LangGraph >= 1.0.1** (2025年10月26日发布)
- **LangGraph-checkpoint-postgres >= 3.0.0**

⚠️ **注意**: 由于使用了较新版本的框架，某些API可能与旧版本不兼容。建议严格按照pyproject.toml中指定的版本安装依赖。

## 🔧 安装配置

### 1. 克隆项目

```bash
git clone <repository-url>
cd NexusAgent
```

### 2. 安装依赖

```bash
# 使用uv包管理器(推荐)
uv pip install -e .

# 或使用pip
pip install -e .
```

**重要提示**: 由于项目使用了较新版本的LangChain和LangGraph，请确保安装的是指定版本的依赖包。如果遇到版本冲突，建议使用虚拟环境：

```bash
# 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
uv pip install -e .
```

### 3. 环境变量配置

创建 `.env` 文件并配置以下环境变量：

```env
# 数据库配置
SQL_USER=your_postgres_user
SQL_PASSWORD=your_postgres_password
SQL_HOST=localhost
SQL_PORT=5432
SQL_DATABASE=nexusagent

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
REDIS_TTL=3600

# API配置
HOST=0.0.0.0
PORT=8001

# 模型API配置
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 4. 数据库初始化

确保PostgreSQL服务正在运行，应用启动时会自动创建必要的表结构。

**注意**: Redis服务需要在启动应用前手动启动，详见下方运行流程。

## 🚀 运行应用

### 完整启动流程

按照以下顺序启动各个服务组件：

#### 1. 启动Redis服务

```bash
# 启动Redis服务器
redis-server

# 或者在后台启动
redis-server --daemonize yes
```

#### 2. 启动后端API服务

```bash
# 使用uv运行主服务
uv run main.py

# 或者使用python直接运行
python main.py
```

服务将在 `http://localhost:8001` 启动

#### 3. 启动前端客户端

```bash
# 使用uv运行前端客户端
uv run frontend/frontend_main.py

# 或者使用python直接运行
python frontend/frontend_main.py
```

### 服务验证

启动完成后，你可以通过以下方式验证服务状态：

1. **检查Redis连接**:

   ```bash
   redis-cli ping
   # 应该返回: PONG
   ```

2. **检查后端API**:

   ```bash
   curl http://localhost:8001/system/info
   # 应该返回系统状态信息
   ```

3. **检查前端客户端**: 前端启动后会显示交互界面，可以输入用户ID开始对话

### 🚀 快速启动指南

如果你想快速体验项目，可以按照以下步骤操作：

```bash
# 1. 确保Redis正在运行
redis-server --daemonize yes

# 2. 在第一个终端启动后端
uv run main.py

# 3. 在第二个终端启动前端
uv run frontend/frontend_main.py

# 4. 在前端界面中：
# - 输入用户ID（或使用默认值）
# - 开始对话，例如："你好，请介绍一下自己"
# - 尝试工具调用："帮我计算 5 乘以 3"
```

## 📖 API文档

### 核心接口

#### 1. 智能代理调用

```http
POST /agent/invoke
Content-Type: application/json

{
    "user_id": "user123",
    "session_id": "session456",
    "query": "帮我查询北京的天气",
    "system_message": "你是一个有用的助手"
}
```

#### 2. 恢复中断的代理

```http
POST /agent/resume
Content-Type: application/json

{
    "user_id": "user123",
    "session_id": "session456",
    "response_type": "accept",
    "args": {}
}
```

#### 3. 获取会话状态

```http
GET /agent/status/{user_id}/{session_id}
```

#### 4. 写入长期记忆

```http
POST /agent/write/longterm
Content-Type: application/json

{
    "user_id": "user123",
    "memory_info": "用户偏好信息"
}
```

### 系统管理接口

- `GET /system/info` - 获取系统信息
- `GET /agent/sessionids/{user_id}` - 获取用户所有会话
- `GET /agent/active/sessionid/{user_id}` - 获取用户活跃会话
- `DELETE /agent/session/{user_id}/{session_id}` - 删除指定会话

## 🔧 核心功能

### 1. 智能代理系统

- 基于LangGraph的ReAct模式代理
- 支持工具调用和多轮对话
- 自动状态管理和错误处理

### 2. 人工审核机制

- 工具调用前的人工确认
- 支持接受、拒绝、编辑参数、直接反馈四种响应
- 多工具调用的批量审核

### 3. 会话管理

- Redis分布式会话存储
- 自动会话恢复和状态同步
- 会话超时和清理机制

### 4. 长期记忆

- PostgreSQL持久化存储
- 用户偏好和历史记录保存
- 智能记忆检索和应用

### 5. 多模型支持

- 统一的模型接口抽象
- 动态模型切换和配置
- 模型性能监控和日志

## 🎯 使用示例

### 基本对话

```python
# 启动前端客户端后
# 输入用户ID: user123
# 输入问题: 你好，请介绍一下自己
```

### 工具调用审核

```python
# 用户: 帮我预订一个酒店
# 系统: 准备调用工具: book_hotel
# 参数: {"hotel_name": "北京大酒店"}
# 您的选择: yes/no/edit/response
```

### 会话管理

```python
# 特殊命令:
# 'status' - 查看当前会话状态
# 'new' - 开始新会话
# 'history' - 恢复历史会话
# 'setting' - 配置用户偏好
# 'exit' - 退出应用
```

## 📊 监控和日志

### 日志系统

- 分级日志记录(DEBUG/INFO/WARNING/ERROR)
- 自动日志轮转和备份
- 详细的请求和响应日志

### 性能监控

- 会话状态实时监控
- 模型调用性能统计
- 系统资源使用情况

## 🔒 安全特性

- 环境变量敏感信息保护
- API密钥安全管理
- 会话隔离和权限控制
- 输入验证和错误处理

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🆘 故障排除

### 常见问题

1. **版本兼容性问题**
   - 确保使用Python >= 3.13
   - 严格按照pyproject.toml中的版本安装依赖
   - 如遇到LangChain/LangGraph版本冲突，请使用虚拟环境
   - 旧版本的LangChain API可能不兼容，建议升级到最新版本

2. **数据库连接失败**
   - 检查PostgreSQL服务状态
   - 验证数据库连接参数
   - 确认数据库用户权限

3. **Redis连接失败**
   - 检查Redis服务状态：`redis-cli ping`
   - 验证Redis连接参数
   - 确保Redis服务在应用启动前已启动
   - 检查防火墙设置

4. **模型API调用失败**
   - 验证API密钥有效性
   - 检查网络连接
   - 确认API配额和限制

5. **工具调用异常**
   - 检查MCP服务器配置
   - 验证工具参数格式
   - 查看详细错误日志

6. **启动顺序问题**
   - 必须按照正确顺序启动：Redis → 后端API → 前端客户端
   - 确保每个服务完全启动后再启动下一个服务

### 日志查看

```bash
# 查看应用日志
tail -f logfile/app.log

# 查看特定级别日志
grep "ERROR" logfile/app.log
```

**NexusAgent** - 让AI代理更智能、更可控、更实用 🤖✨
