import time


from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional

from langgraph.types import Command

from utils.memory_service import get_memory_service
from utils.logger_manager import LoggerManager
from utils.data_models import AgentResponse, AgentRequest, InterruptResponse, SessionStatusResponse, ActiveSessionInfoResponse, SessionInfoResponse, LongMemRequest
from utils.message_tools import async_parse_messages
from configs.configuration import ConfigRedis


# 设置日志
logger = LoggerManager.get_logger(name=__name__)


router = APIRouter(prefix="/agent", tags=["agent"])


async def process_agent_result(
        session_id: str,
        result: Dict[str, Any],
        state: Any,
        user_id: Optional[str] = None
) -> AgentResponse:
    """
    处理智能体返回结果
    Args:
        session_id: 会话唯一标识
        result: 智能体返回结果
        state: 应用状态实例
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
    exists = await state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    if exists:
        status = response.status
        last_query = None
        last_response = response
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

    return response


@router.post("/invoke", response_model=AgentResponse)
async def invoke_agent(request: AgentRequest, app_request: Request):
    """
    创建智能体并调用，直接返回结果或中断数据
    Args:
        request: 客户端发起的智能体请求
        app_request: 应用请求
    Returns:
        AgentResponse: 智能体响应
    """
    logger.info(f"调用/agent/invoke接口，创建智能体并调用，直接返回结果或中断数据，接受到前端用户请求:{request}")
    # 获取用户请求中的user_id和session_id
    user_id = request.user_id
    session_id = request.session_id
    state = app_request.app.state
    # 调用函数获取长期记忆
    memory_service = get_memory_service(state=state)
    result = await memory_service.read_long_term_info(user_id=user_id)
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
    exists = await state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)

    # 若用户会话不存在 则创建新会话
    if not exists:
        status = "idle"
        last_query = None
        last_response = None
        last_updated = time.time()
        ttl = ConfigRedis.TTL
        await state.session_manager.create_session(
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
    await state.session_manager.update_session(
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
        result = await state.agent.ainvoke({"messages": messages}, config={"configurable": {"thread_id": session_id}})
        # 将返回的messages进行格式化输出 方便查看调试
        await async_parse_messages(result['messages'])

        # 再处理结果并更新会话状态
        return await process_agent_result(
            session_id=session_id,
            result=result,
            user_id=user_id,
            state=state
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
        await state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

        return error_response


@router.post("/resume", response_model=AgentResponse)
async def resume_agent(response: InterruptResponse, app_request: Request):
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
    state = app_request.app.state
    # 判断当前用户会话是否存在
    exists = await state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    # 若用户会话不存在 则抛出异常
    if not exists:
        logger.error(f"status_code=404,用户会话 {user_id}:{session_id} 不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id}:{session_id} 不存在")

    # 检查会话状态是否为中断 若不是中断则抛出异常
    session = await state.session_manager.get_session(user_id=user_id, session_id=session_id)
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
    await state.session_manager.update_session(
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
            result = await state.agent.ainvoke(
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
            result = await state.agent.ainvoke(
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
            result = await state.agent.ainvoke(
                Command(resume=command_data),
                config={"configurable": {"thread_id": session_id}}
            )
        # 将返回的messages进行格式化输出 方便查看调试
        await async_parse_messages(result['messages'])
        # 再处理结果并更新会话状态
        return await process_agent_result(
            session_id=session_id,
            result=result,
            user_id=user_id,
            state=state
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
        await state.session_manager.update_session(
            user_id=user_id,
            session_id=session_id,
            status=status,
            last_query=last_query,
            last_response=last_response,
            last_updated=last_updated,
            ttl=ttl
        )

        return error_response


@router.get("/status/{user_id}/{session_id}", response_model=SessionStatusResponse)
async def get_agent_status(user_id: str, session_id: str, app_request: Request):
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
    state = app_request.app.state
    # 判断当前用户会话是否存在
    exists = await state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
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
    session = await state.session_manager.get_session(user_id=user_id, session_id=session_id)
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


@router.get("/active/sessionid/{user_id}", response_model=ActiveSessionInfoResponse)
async def get_agent_active_sessionid(user_id: str, app_request: Request):
    """
    获取指定用户当前最近一次更新的会话ID
    Args:
        user_id: 用户唯一标识
    Returns:
        ActiveSessionInfoResponse: 当前最近一次更新的会话ID响应
    """
    logger.info(
        f"调用/agent/active/sessionid/接口，获取指定用户当前最近一次更新的会话ID，接受到前端用户请求:{user_id}")
    state = app_request.app.state
    # 判断当前用户是否存在
    exists = await state.session_manager.user_id_exists(user_id=user_id)
    # 若用户不存在 构造ActiveSessionInfoResponse对象
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        return ActiveSessionInfoResponse(
            active_session_id=""
        )
    # 若会话存在 构造ActiveSessionInfoResponse对象
    response = ActiveSessionInfoResponse(
        active_session_id=await state.session_manager.get_user_active_session_id(user_id=user_id)
    )
    logger.info(f"返回当前用户的激活的会话ID:{response}")
    return response


@router.get("/sessionids/{user_id}", response_model=SessionInfoResponse)
async def get_agent_sessionids(user_id: str, app_request: Request):
    """
    获取指定用户的所有会话ID
    Args:
        user_id: 用户唯一标识
    Returns:
        SessionInfoResponse: 所有会话ID响应
    """
    logger.info(f"调用/agent/sessionids/接口，获取指定用户的所有会话ID，接受到前端用户请求:{user_id}")
    state = app_request.app.state
    # 判断当前用户是否存在
    exists = await state.session_manager.user_id_exists(user_id=user_id)
    # 若用户不存在 构造SessionInfoResponse对象
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        return SessionInfoResponse(
            session_ids=[]
        )
    # 若会话存在 构造SessionInfoResponse对象
    response = SessionInfoResponse(
        session_ids=await state.session_manager.get_all_session_ids(user_id=user_id)
    )
    logger.info(f"返回当前用户的所有会话ID:{response}")
    return response


@router.delete("/session/{user_id}/{session_id}")
async def delete_agent_session(user_id: str, session_id: str, app_request: Request):
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
    state = app_request.app.state
    # 判断当前用户会话是否存在
    exists = await state.session_manager.session_id_exists(user_id=user_id, session_id=session_id)
    # 如果不存在,则抛出异常
    if not exists:
        logger.error(f"用户 {user_id}:{session_id} 的会话不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id}:{session_id} 不存在")

    # 若会话存在 则删除会话
    await state.session_manager.delete_session(user_id=user_id, session_id=session_id)
    response = {
        "status": "success",
        "message": f"用户 {user_id}:{session_id} 的会话已删除"
    }
    logger.info(f"用户会话已经删除:{response}")
    return response


@router.post("/write/longterm")
async def write_long_term(request: LongMemRequest, app_request: Request):
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
    state = app_request.app.state
    # 判断当前用户会话是否存在
    exists = await state.session_manager.user_id_exists(user_id=user_id)
    # 如果不存在 则抛出异常
    if not exists:
        logger.error(f"用户 {user_id} 的会话不存在")
        raise HTTPException(
            status_code=404, detail=f"用户会话 {user_id} 不存在")

    # 写入指定用户长期记忆内容
    memory_service = get_memory_service(state=state)
    result = await memory_service.write_long_term_info(user_id=user_id, memory_info=memory_info)
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
