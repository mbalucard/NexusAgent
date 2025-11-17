import json
from langchain.tools import tool, BaseTool
from pydantic import BaseModel, Field
from typing import Optional
from httpx import AsyncClient

from configs.request_configs import test_env

class InstitutionListArgs(BaseModel):
    authorization: str = Field(..., description="授权，以Bearer开头的字符串，必须")
    parentId: Optional[int] = Field(None, description="机构ID，若不提供则返回全量机构列表")

@tool("institution_list", description="机构及部门列表", args_schema=InstitutionListArgs)
async def institution_list(
    authorization: str,
    parentId: int = None
):
    """
    机构及部门列表
    Args:
        authorization (str): 授权token
        parentId (int, optional): 机构ID. Defaults to None.
    Returns:
        dict: 机构及部门列表
    """
    org_list_payload = json.dumps({
        "parentId": parentId,
    })
    org_list_headers = {
        'Content-Type': test_env["content_type"],
        'Tenant-Id': test_env["tenant_id"],
        'Authorization': authorization
    }
    
    if parentId:
        org_list_url = f"{test_env['url']}/organization/list"
    else:
        org_list_url = f"{test_env['url']}/organization/list-all"

    
    async with AsyncClient() as client:
        response = await client.post(org_list_url, headers=org_list_headers, data=org_list_payload)

    return response.json()