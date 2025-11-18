import json
from langchain.tools import tool, BaseTool
from pydantic import BaseModel, Field
from typing import Optional
from httpx import AsyncClient

from configs.request_configs import test_env


class UserListArgs(BaseModel):
    authorization: str = Field(..., description="授权token，以Bearer开头的字符串")
    organId: Optional[int] = Field(
        None, description="机构ID，不提供则查询所有用户信息，含离职员工")
    current: int = Field(1, ge=1, description="页码")
    keyword: str = Field("", description="搜索用关键字")
    size: int = Field(100, ge=10, le=1000, description="每页条数，每页获取的用户数量")


@tool("user_list", description="获取用户列表明细", args_schema=UserListArgs)
async def user_list(
        authorization: str,
        organId: int = None,
        current: int = 1,
        keyword: str = "",
        size: int = 100):
    """
    用户列表
    Args:
        authorization (str): 授权token，必填
        organId (int, optional): 机构ID.
        current (int, optional): 页码，
        keyword (str, optional): 搜索用关键字. 
        size (int, optional): 每页条数，每页获取的用户数量
    Returns:
        dict: 用户列表
    """
    if organId:
        user_list_url = f"{test_env['url']}/organization/user-list"
    else:
        user_list_url = f"{test_env['url']}/user/list"
    user_list_payload = json.dumps({
        "organId": organId,  # 机构ID
        "current": current,  # 当前页
        "keyword": keyword,  # 搜索用关键字
        "size": size  # 每页条数
    })
    user_list_headers = {
        'Content-Type': test_env["content_type"],
        'Tenant-Id': test_env["tenant_id"],
        'Authorization': authorization
    }
    async with AsyncClient() as client:
        response = await client.post(user_list_url, headers=user_list_headers, data=user_list_payload)

    return response.json()
