import time

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from utils.file_tools import read_md_file

from configs.configuration import FilePath

class AgentRequest(BaseModel):
    """
    定义数据模型 智能体请求的输入
    """
    user_id: str  # 用户唯一标识
    session_id: str  # 会话唯一标识
    query: str  # 用户问题
    system_message: Optional[str] = read_md_file(FilePath.SYSTEM_MESSAGE_PATH)  # 系统提示词
    parameter_info: Optional[Dict[str, Any]] = None  # 参数信息



class LongMemRequest(BaseModel):
    """
    定义数据模型 写入长期记忆的请求输入
    """
    user_id: str  # 用户唯一标识
    memory_info: str  # 长期记忆内容


class AgentResponse(BaseModel):
    """
    定义数据模型 智能体返回的响应结果
    """
    session_id: str  # 会话唯一标识
    status: str  # 三个状态：interrupted, completed, error
    timestamp: float = Field(default_factory=lambda: time.time())  # 时间戳
    message: Optional[str] = None  # error时的提示消息
    result: Optional[Dict[str, Any]] = None  # completed时的结果消息
    interrupt_data: Optional[Dict[str, Any]] = None  # interrupted时的中断消息


class InterruptResponse(BaseModel):
    """
    定义数据模型 客户端发起的恢复智能体运行的中断反馈请求数据
    """
    user_id: str  # 用户唯一标识
    session_id: str  # 会话唯一标识
    # 响应类型：accept(允许调用), edit(调整工具参数，此时args中携带修改后的调用参数)，reject(不允许调用)
    response_type: str
    args: Optional[Dict[str, Any]] = None  # 如果是edit可能需要额外的参数
    interrupt_id: Optional[str] = None  # 中断ID，处理多个中断时需要
    interrupt_responses: Optional[Dict[str, Dict[str, Any]]] = None  # 多个中断的响应映射，格式: {interrupt_id: {type: "accept/reject/edit", args: {...}}}


class SystemInfoResponse(BaseModel):
    """
    定义数据模型 系统信息响应
    """
    sessions_count: int  # 当前会话数量
    active_users: Optional[Dict[str, Any]] = None  # 当前活跃用户列表


class SessionInfoResponse(BaseModel):
    """
    定义数据模型 所有会话ID响应数据
    """
    session_ids: List[str]  # 当前用户的所有session_id


class ActiveSessionInfoResponse(BaseModel):
    """
    定义数据模型 当前最近一次更新的会话ID响应
    """
    active_session_id: str  # 最近一次更新的会话ID


class SessionStatusResponse(BaseModel):
    """
    定义数据模型 会话状态响应
    """
    user_id: str  # 用户唯一标识
    session_id: Optional[str] = None  # 会话唯一标识
    status: str  # 会话状态：not_found, idle, running, interrupted, completed, error
    message: Optional[str] = None  # error时的提示消息
    last_query: Optional[str] = None  # 最后一次查询
    last_updated: Optional[float] = None  # 最后一次更新时间
    last_response: Optional[AgentResponse] = None  # 最后一次响应


if __name__ == "__main__":
    request = AgentRequest(user_id="123", session_id="456", query="你好")
    print(request)