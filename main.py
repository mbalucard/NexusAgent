import logging
import uuid
import time
import uvicorn

from concurrent_log_handler import ConcurrentRotatingFileHandler
from fastapi import HTTPException, FastAPI
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool

from configs.configuration import ConfigLogFile, DatabaseConfig, ConfigRedis, ConfigAPI
from configs.model_configs import ModelParameter
from utils.redis_manager import get_session_manager
from utils.data_models import AgentResponse, AgentRequest, InterruptResponse, SessionStatusResponse, ActiveSessionInfoResponse, SessionInfoResponse, SystemInfoResponse, LongMemRequest
from utils.llms import get_llm
from utils.tools import get_tools
from utils.message_tools import trimmed_messages_hook, async_parse_messages

from langgraph.types import Command
from langchain.agents import create_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

# 设置日志
logger = logging.getLogger(__name__)
# 日志级别设置，DEBUG，INFO，WARNING，ERROR，CRITICAL
logger.setLevel(logging.DEBUG)
logger.handlers = []  # 清空默认处理器
handler = ConcurrentRotatingFileHandler(
    ConfigLogFile.LOG_FILE_PATH,  # 日志文件路径
    maxBytes=ConfigLogFile.MAX_BYTES,  # 日志文件最大大小
    backupCount=ConfigLogFile.BACKUP_COUNT  # 日志文件备份数量
)
# 设置处理级别为DEBUG
handler.setLevel(logging.DEBUG)
# 设置日志格式
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
# 添加处理器到日志
logger.addHandler(handler)


async def process_agent_result(
        session_id: str,
        result: Dict[str, Any],
        user_id: Optional[str] = None) -> AgentResponse:
    """
    处理智能体返回结果
    Args:
        session_id: 会话唯一标识
        result: 智能体返回结果
        user_id: 用户唯一标识
    Returns:
        AgentResponse: 智能体返回结果
    """
    response = None
    try:
        # 检查是否有中断
        if "__interrupt__" in result:
            interrupts = result["__interrupt__"]

            # 如果有多个中断，需要特殊处理
            if len(interrupts) > 1:
                # 收集所有中断数据
                all_interrupt_data = []
                for interrupt in interrupts:
                    interrupt_data = interrupt.value
                    if "interrupt_type" not in interrupt_data:
                        interrupt_data["interrupt_type"] = "unknown"
                    # 添加中断ID
                    interrupt_data["interrupt_id"] = interrupt.id
                    all_interrupt_data.append(interrupt_data)

                # 返回多中断信息
                response = AgentResponse(
                    session_id=session_id,
                    status="interrupted",
                    interrupt_data={
                        "multiple_interrupts": True,
                        "interrupts": all_interrupt_data,
                        "description": f"检测到{len(interrupts)}个工具调用需要审核"
                    }
                )
                logger.info(f"当前触发多个工具调用中断，共{len(interrupts)}个:{response}")
            else:
                # 单个中断的处理逻辑
                interrupt_data = interrupts[0].value
                if "interrupt_type" not in interrupt_data:
                    interrupt_data["interrupt_type"] = "unknown"
                # 添加中断ID
                interrupt_data["interrupt_id"] = interrupts[0].id

                response = AgentResponse(
                    session_id=session_id,
                    status="interrupted",
                    interrupt_data=interrupt_data
                )
                logger.info(f"当前触发工具调用中断:{response}")
        # 如果没有中断，返回最终结果
        else:
            response = AgentResponse(
                session_id=session_id,
                status="completed",
                result=result
            )
            logger.info(f"最终智能体回复结果:{response}")
    except Exception as e:
        response = AgentResponse(
            session_id=session_id,
            status="error",
            message=f"处理智能体结果时出错: {str(e)}"
        )
        logger.error(f"处理智能体结果时发生错误: {response}")

    # 若会话存在，更新会话状态
    exists = await app.state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    if exists:
        status = response.status
        last_query = None
        last_response = response
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await app.state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

    return response


async def read_long_term_info(user_id: str):
    """
    读取指定用户长期记忆中的内容

    Args:
        user_id: 用户的唯一标识

    Returns:
        Dict[str, Any]: 包含记忆内容和状态的响应
    """
    try:
        # 指定命名空间
        namespace = ("memories", user_id)
        # 搜索记忆内容
        memories = await app.state.store.asearch(namespace, query="")
        # 处理查询结果
        if memories is None:
            raise HTTPException(status_code=500, detail="查询返回无效结果，可能是存储系统错误。")
        # 提取并拼接记忆内容
        long_term_info = " ".join(
            [d.value["data"] for d in memories if isinstance(
                d.value, dict) and "data" in d.value]
        ) if memories else ""
        # 记录查询成功的日志
        logger.info(
            f"成功获取用户ID: {user_id} 的长期记忆，内容长度: {len(long_term_info)} 字符")
        # 返回结构化响应
        return {
            "success": True,
            "user_id": user_id,
            "long_term_info": long_term_info,
            "message": "长期记忆获取成功" if long_term_info else "未找到长期记忆内容"
        }
    except Exception as e:
        # 处理其他未预期的错误
        logger.error(f"获取用户ID: {user_id} 的长期记忆时发生意外错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取长期记忆失败: {str(e)}")


async def write_long_term_info(user_id: str, memory_info: str):
    """
    写入指定用户长期记忆内容
    Args:
        user_id: 用户的唯一标识
        memory_info: 要保存的记忆内容
    Returns:
        Dict[str, Any]: 包含成功状态和存储记忆ID的响应
    """
    try:
        # 生成命名空间和唯一记忆ID
        namespace = ("memories", user_id)
        memory_id = str(uuid.uuid4())
        # 存储数据到指定命名空间
        result = await app.state.store.aput(
            namespace=namespace,
            key=memory_id,
            value={"data": memory_info}
        )
        # 记录存储成功的日志
        logger.info(f"成功为用户ID: {user_id} 存储记忆，记忆ID: {memory_id}")
        # 返回结构化响应
        return {
            "success": True,
            "memory_id": memory_id,
            "message": "记忆存储成功"
        }
    except Exception as e:
        # 处理其他未预期的错误
        logger.error(f"存储用户ID: {user_id} 的记忆时发生意外错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"存储记忆失败: {str(e)}")


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
            tools = await get_tools()

            app.state.agent = create_agent(
                model=llm_chat,
                tools=tools,
                middleware=[trimmed_messages_hook],
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


@app.post("/agent/invoke", response_model=AgentResponse)
async def invoke_agent(request: AgentRequest):
    """
    创建智能体并调用，直接返回结果或中断数据
    Args:
        request: 客户端发起的智能体请求
    Returns:
        AgentResponse: 智能体响应
    """
    logger.info(f"调用/agent/invoke接口，创建智能体并调用，直接返回结果或中断数据，接受到前端用户请求:{request}")
    # 获取用户请求中的user_id和session_id
    user_id = request.user_id
    session_id = request.session_id
    # 调用函数获取长期记忆
    result = await read_long_term_info(user_id=user_id)
    # 检查返回结果是否成功
    if result.get("success", False):
        long_term_info = result.get("long_term_info")
        # 若获取到的内容不为空 则将记忆内容拼接到系统提示词中
        if long_term_info:
            system_message = f"{request.system_message}我的附加信息有:{long_term_info}"
            logger.info(f"获取用户偏好配置数据，system_message的信息为:{system_message}")
        # 若获取到的内容为空，则直接使用系统提示词
        else:
            system_message = request.system_message
            logger.info(f"未获取到用户偏好配置数据，system_message的信息为:{system_message}")
    else:
        system_message = request.system_message
        logger.info(f"未获取到用户偏好配置数据，system_message的信息为:{system_message}")

    # 判断当前用户会话是否存在
    exists = await app.state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)

    # 若用户会话不存在 则创建新会话
    if not exists:
        status = "idle"
        last_query = None
        last_response = None
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await app.state.session_manager.create_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

    # 新请求统一更新会话信息
    status = "running"
    last_query = request.query
    last_response = None
    last_updated = time.time()
    ttl = ConfigRedis.TTL
    await app.state.session_manager.update_session(
        user_id=user_id,
        session_id=session_id,
        status=status,
        last_query=last_query,
        last_response=last_response,
        last_updated=last_updated,
        ttl=ttl
    )

    # 构造智能体输入消息体
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": request.query}
    ]

    try:
        # 先调用智能体
        result = await app.state.agent.ainvoke({"messages": messages}, config={"configurable": {"thread_id": session_id}})
        # 将返回的messages进行格式化输出 方便查看调试
        await async_parse_messages(result['messages'])

        # 再处理结果并更新会话状态
        return await process_agent_result(
            session_id=session_id,
            result=result,
            user_id=user_id
        )

    except Exception as e:
        # 异常处理
        error_response = AgentResponse(
            session_id=session_id,
            status="error",
            message=f"处理请求时出错: {str(e)}"
        )
        logger.error(f"处理请求时出错: {error_response}")

        # 更新会话状态
        status = "error"
        last_query = None
        last_response = error_response
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await app.state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

        return error_response


@app.post("/agent/resume", response_model=AgentResponse)
async def resume_agent(response: InterruptResponse):
    """
    恢复被中断的智能体运行并等待运行完成或再次中断
    Args:
        response: 客户端发起的恢复智能体执行的请求
    Returns:
        AgentResponse: 智能体响应
    """
    logger.info(
        f"调用/agent/resume接口，恢复被中断的智能体运行并等待运行完成或再次中断，接受到前端用户请求:{response}")
    # 获取用户请求中的user_id和session_id
    user_id = response.user_id
    session_id = response.session_id

    # 判断当前用户会话是否存在
    exists = await app.state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    # 若用户会话不存在 则抛出异常
    if not exists:
        logger.error(f"status_code=404,用户会话 {user_id}:{session_id} 不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id}:{session_id} 不存在")

    # 检查会话状态是否为中断 若不是中断则抛出异常
    session = await app.state.session_manager.get_session(user_id=user_id, session_id=session_id)
    status = session.get("status")
    if status != "interrupted":
        logger.error(f"status_code=400,会话当前状态为 {status}，无法恢复非中断状态的会话")
        raise HTTPException(
            status_code=400, detail=f"会话当前状态为 {status}，无法恢复非中断状态的会话")

    # 更新会话状态
    status = "running"
    last_query = None
    last_response = None
    last_updated = time.time()
    ttl = ConfigRedis.TTL
    await app.state.session_manager.update_session(
        user_id=user_id,
        session_id=session_id,
        status=status,
        last_query=last_query,
        last_response=last_response,
        last_updated=last_updated,
        ttl=ttl
    )

    try:
        # 构造响应数据
        if response.interrupt_responses:
            # 处理多个中断的情况
            command_data = response.interrupt_responses
            logger.info(f"恢复多个中断执行，中断响应数据: {command_data}")
            result = await app.state.agent.ainvoke(
                Command(resume=command_data),
                config={"configurable": {"thread_id": session_id}}
            )
        elif response.interrupt_id:
            # 处理单个指定中断ID的情况
            command_data = {
                response.interrupt_id: {
                    "type": response.response_type,
                    **(response.args or {})
                }
            }
            logger.info(
                f"恢复指定中断执行，中断ID: {response.interrupt_id}, 响应数据: {command_data}")
            result = await app.state.agent.ainvoke(
                Command(resume=command_data),
                config={"configurable": {"thread_id": session_id}}
            )
        else:
            # 原有的单中断处理逻辑（向后兼容）
            command_data = {
                "type": response.response_type
            }
            if response.args:
                command_data["args"] = response.args

            logger.info(f"恢复单个中断执行（兼容模式），响应数据: {command_data}")
            result = await app.state.agent.ainvoke(
                Command(resume=command_data),
                config={"configurable": {"thread_id": session_id}}
            )
        # 将返回的messages进行格式化输出 方便查看调试
        await async_parse_messages(result['messages'])
        # 再处理结果并更新会话状态
        return await process_agent_result(
            session_id=session_id,
            result=result,
            user_id=user_id
        )

    except Exception as e:
        # 异常处理
        error_response = AgentResponse(
            session_id=session_id,
            status="error",
            message=f"恢复执行时出错: {str(e)}"
        )
        logger.error(f"处理请求时出错: {error_response}")

        # 更新会话状态
        status = "error"
        last_query = None
        last_response = error_response
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await app.state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

        return error_response


@app.get("/agent/status/{user_id}/{session_id}", response_model=SessionStatusResponse)
async def get_agent_status(user_id: str, session_id: str):
    """
    获取指定用户当前会话的状态数据
    Args:
        user_id: 用户唯一标识
        session_id: 会话唯一标识
    Returns:
        SessionStatusResponse: 会话状态响应
    """
    logger.info(
        f"调用/agent/status/接口，获取指定用户当前会话的状态数据，接受到前端用户请求:{user_id}:{session_id}")
    # 判断当前用户会话是否存在
    exists = await app.state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    # 若会话不存在 构造SessionStatusResponse对象
    if not exists:
        logger.error(f"用户 {user_id}:{session_id} 的会话不存在")
        return SessionStatusResponse(
            user_id=user_id,
            session_id=session_id,
            status="not_found",
            message=f"用户 {user_id}:{session_id} 的会话不存在"
        )

    # 若会话存在 构造SessionStatusResponse对象
    session = await app.state.session_manager.get_session(user_id=user_id, session_id=session_id)
    response = SessionStatusResponse(
        user_id=user_id,
        session_id=session_id,
        status=session.get("status"),
        last_query=session.get("last_query"),
        last_updated=session.get("last_updated"),
        last_response=session.get("last_response")
    )
    logger.info(f"返回当前用户的会话状态:{response}")
    return response


@app.get("/agent/active/sessionid/{user_id}", response_model=ActiveSessionInfoResponse)
async def get_agent_active_sessionid(user_id: str):
    """
    获取指定用户当前最近一次更新的会话ID
    Args:
        user_id: 用户唯一标识
    Returns:
        ActiveSessionInfoResponse: 当前最近一次更新的会话ID响应
    """
    logger.info(
        f"调用/agent/active/sessionid/接口，获取指定用户当前最近一次更新的会话ID，接受到前端用户请求:{user_id}")
    # 判断当前用户是否存在
    exists = await app.state.session_manager.user_id_exists(user_id=user_id)
    # 若用户不存在 构造ActiveSessionInfoResponse对象
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        return ActiveSessionInfoResponse(
            active_session_id=""
        )
    # 若会话存在 构造ActiveSessionInfoResponse对象
    response = ActiveSessionInfoResponse(
        active_session_id=await app.state.session_manager.get_user_active_session_id(user_id=user_id)
    )
    logger.info(f"返回当前用户的激活的会话ID:{response}")
    return response


@app.get("/agent/sessionids/{user_id}", response_model=SessionInfoResponse)
async def get_agent_sessionids(user_id: str):
    """
    获取指定用户的所有会话ID
    Args:
        user_id: 用户唯一标识
    Returns:
        SessionInfoResponse: 所有会话ID响应
    """
    logger.info(f"调用/agent/sessionids/接口，获取指定用户的所有会话ID，接受到前端用户请求:{user_id}")
    # 判断当前用户是否存在
    exists = await app.state.session_manager.user_id_exists(user_id=user_id)
    # 若用户不存在 构造SessionInfoResponse对象
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        return SessionInfoResponse(
            session_ids=[]
        )
    # 若会话存在 构造SessionInfoResponse对象
    response = SessionInfoResponse(
        session_ids=await app.state.session_manager.get_all_session_ids(user_id=user_id)
    )
    logger.info(f"返回当前用户的所有会话ID:{response}")
    return response


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


@app.delete("/agent/session/{user_id}/{session_id}")
async def delete_agent_session(user_id: str, session_id: str):
    """
    删除指定用户当指定session_id的会话
    Args:
        user_id: 用户唯一标识
        session_id: 会话唯一标识
    Returns:
        dict: 删除结果
    """
    logger.info(
        f"调用/agent/session/接口，删除指定用户指定session_id的会话，接受到前端用户请求:{user_id}:{session_id}")
    # 判断当前用户会话是否存在
    exists = await app.state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    # 如果不存在,则抛出异常
    if not exists:
        logger.error(f"用户 {user_id}:{session_id} 的会话不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id}:{session_id} 不存在")

    # 若会话存在 则删除会话
    await app.state.session_manager.delete_session(user_id=user_id, session_id=session_id)
    response = {
        "status": "success",
        "message": f"用户 {user_id}:{session_id} 的会话已删除"
    }
    logger.info(f"用户会话已经删除:{response}")
    return response


@app.post("/agent/write/longterm")
async def write_long_term(request: LongMemRequest):
    """
    写入指定用户的长期记忆内容
    Args:
        request: 客户端发起的写入长期记忆的请求
    Returns:
        dict: 写入结果
    """
    logger.info(f"调用/agent/write/longterm接口，写入指定用户的长期记忆内容，接受到前端用户请求:{request}")
    # 获取用户请求中的user_id和memory_info
    user_id = request.user_id
    memory_info = request.memory_info

    # 判断当前用户会话是否存在
    exists = await app.state.session_manager.user_id_exists(user_id=user_id)
    # 如果不存在 则抛出异常
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id} 不存在")

    # 写入指定用户长期记忆内容
    result = await write_long_term_info(user_id=user_id, memory_info=memory_info)
    # 检查返回结果是否成功
    if result.get("success", False):
        # 构造成功响应
        return {
            "status": "success",
            "memory_id": result.get("memory_id"),
            "message": result.get("message", "记忆存储成功")
        }
    else:
        # 处理非成功返回结果
        raise HTTPException(
            status_code=500,
            detail="记忆存储失败，返回结果未包含成功状态"
        )


if __name__ == "__main__":

    uvicorn.run(app, host=ConfigAPI.HOST, port=ConfigAPI.PORT)
