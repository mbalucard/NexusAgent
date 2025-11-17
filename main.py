import uvicorn

from fastapi import FastAPI
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from routes.agent import router as agent_router

from configs.configuration import DatabaseConfig,  ConfigAPI
from configs.model_configs import ModelParameter
from utils.redis_manager import get_session_manager
from utils.llms import get_llm
from tools import get_tool_interrupt_configuration, get_all_tools
from utils.message_tools import trimmed_messages_hook
from utils.logger_manager import LoggerManager
from utils.data_models import SystemInfoResponse

from langchain.agents import create_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from langchain.agents.middleware import HumanInTheLoopMiddleware


# 设置日志
logger = LoggerManager.get_logger(name=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器,app应用初始化函数
    """
    try:
        # 实例化异步Redis会话管理，并存储为单实例
        app.state.session_manager = get_session_manager()

        # LLM模型初始化
        llm_chat, llm_embedding = get_llm(
            chat_model_type=ModelParameter.DEFAULT_LLM_TYPE, embedding_model_type=ModelParameter.DEFAULT_EMBEDDING_MODEL,
            temperature=ModelParameter.DEFAULT_TEMPERATURE)
        logger.info("LLM模型初始化成功")

        # 创建数据库连接池 动态连接池根据负载调整连接池大小
        async with AsyncConnectionPool(
                conninfo=DatabaseConfig.DB_URI,
                min_size=DatabaseConfig.MIN_SIZE,
                max_size=DatabaseConfig.MAX_SIZE,
                kwargs={"autocommit": True, "prepare_threshold": 0}) as pool:
            # 短期记忆，初始化checkpointer,并初始化表结构(如果表不存在)
            app.state.checkpointer = AsyncPostgresSaver(pool)
            await app.state.checkpointer.setup()
            logger.info("短期记忆Checkpointer初始化成功")

            # 长期记忆，初始化store,并初始化表结构(如果表不存在)
            app.state.store = AsyncPostgresStore(pool)
            await app.state.store.setup()
            logger.info("长期记忆store初始化成功")

            # 获取工具列表
            tools = await get_all_tools()
            interrupt_configuration = await get_tool_interrupt_configuration()
            app.state.agent = create_agent(
                model=llm_chat,
                tools=tools,
                middleware=[trimmed_messages_hook, HumanInTheLoopMiddleware(
                    interrupt_on=interrupt_configuration, description_prefix="Tool execution requires approval")],
                checkpointer=app.state.checkpointer,
                store=app.state.store
            )
            logger.info("Agent初始化成功")
            logger.info("服务完成初始化，并启动服务")
            yield
    except Exception as e:
        logger.error(f"初始化失败: {str(e)}")
        raise RuntimeError(f"服务初始化失败: {str(e)}")

    # 清理资源
    finally:
        # 关闭Redis连接
        await app.state.session_manager.close()
        # 关闭PostgreSQL连接池
        await pool.close()
        logger.info("关闭服务并完成资源清理")


# 定义Agent智能体后端API接口服务路由
app = FastAPI(
    title="Agent智能体后端API接口服务",
    description="基于LangGraph提供AI Agent服务",
    lifespan=lifespan
)
# 注册Agent智能体后端API接口服务路由
app.include_router(agent_router)


@app.get("/system/info", response_model=SystemInfoResponse)
async def get_system_info():
    """
    获取当前系统内全部的会话状态信息
    Returns:
        SystemInfoResponse: 系统信息响应
    """
    logger.info(f"调用/system/info接口，获取当前系统内全部的会话状态信息")
    # 构造SystemInfoResponse对象
    response = SystemInfoResponse(
        sessions_count=await app.state.session_manager.get_session_count(),  # 当前系统内会话总数
        # 系统内当前活跃的用户和会话
        active_users=await app.state.session_manager.get_all_users_session_ids()
    )
    logger.info(f"返回当前系统状态信息:{response}")
    return response


if __name__ == "__main__":

    uvicorn.run(app, host=ConfigAPI.HOST, port=ConfigAPI.PORT)
