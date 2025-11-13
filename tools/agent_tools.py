from langchain_mcp_adapters.client import MultiServerMCPClient

from configs.mcp_server import mcp_server_configs
from tools.custom_tools import review_tools, normal_tools
from utils.logger_manager import LoggerManager

# 设置日志
logger = LoggerManager.get_logger(name=__name__)


def get_interrupt_args(tool_list: list):
    """
    生成中断配置,适配langchain 1.0 的中间件
    Args:
        tool_list: 工具列表
    Returns:
        interrupt_args: 中断配置
    """
    interrupt_args = {}
    for i in tool_list:
        interrupt_args[i.name] = {
            "allowed_decisions": ["approve", "reject", "edit"],
            "description": f"{i.description},Tool execution requires approval"
        }
    return interrupt_args


async def get_tool_interrupt_configuration():
    """
    获取工具中断配置
    Returns:
        interrupt_configuration: 中断配置
    """
    client = MultiServerMCPClient(
        mcp_server_configs
    )
    mcp_server_tools = await client.get_tools()
    tools_list = mcp_server_tools
    tools_list.extend(review_tools)
    interrupt_configuration = get_interrupt_args(tools_list)
    return interrupt_configuration


async def get_all_tools():
    """
    获取所有工具列表
    """
    client = MultiServerMCPClient(
        mcp_server_configs
    )
    mcp_server_tools = await client.get_tools()
    tools = mcp_server_tools
    tools.extend(review_tools)
    tools.extend(normal_tools)
    return tools


if __name__ == "__main__":
    import asyncio
    tools = asyncio.run(get_all_tools())
    for tool in tools:
        print(f"工具名称 (Name): {tool.name}")
        print(f"工具描述 (Description): {tool.description}")
        print(f"工具参数 (Args): {tool.args}")
        print("=" * 30)  # 打印分隔线
