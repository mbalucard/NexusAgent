from typing import Callable

from langchain.tools import BaseTool, tool as create_tool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.interrupt import HumanInterrupt, HumanInterruptConfig
from langgraph.types import interrupt, Command
from langchain_mcp_adapters.client import MultiServerMCPClient

from configs.mcp_server import mcp_server_configs
from utils.custom_tools import review_tools, normal_tools
from utils.logger_manager import LoggerManager

# 设置日志
logger = LoggerManager.get_logger(name=__name__)


async def add_human_in_the_loop(tool: Callable | BaseTool, *, interrupt_config: HumanInterruptConfig = None) -> BaseTool:
    """
    为工具添加人工审查(human-in-the-loop)

    Args:
        tool: 可调用对象或 BaseTool 对象
        interrupt_config: 可选的人工中断配置

    Returns:
        BaseTool: 一个带有人工审查功能的 BaseTool 对象
    """
    # 检查传入的工具是否为 BaseTool 的实例
    if not isinstance(tool, BaseTool):
        # 如果不是 BaseTool，则将可调用对象转换为 BaseTool 对象
        tool = create_tool(tool)

    # 使用 create_tool 装饰器定义一个新的工具函数，继承原工具的名称、描述和参数模式
    @create_tool(
        tool.name,
        description=tool.description,
        args_schema=tool.args_schema
    )
    async def call_tool_with_interrupt(config: RunnableConfig, **tool_input):
        """
        处理带有中断逻辑的工具调用.
        args:
            config: RunnableConfig 对象
            **tool_input: 工具输入参数
        returns:
            工具的响应结果
        """
        # 构建中断请求
        request: HumanInterrupt = {
            "action_request": {
                "action": tool.name,
                "args": tool_input
            },
            "config": interrupt_config,
            "description": f"准备调用工具: {tool.name} \n 参数: {tool_input} \n 输入 'yes' 接受工具调用\n输入 'no' 拒绝工具调用\n输入 'edit' 修改工具参数后调用工具\n输入 'response' 不调用工具直接反馈信息",
        }
        # 调用 interrupt 函数，获取人工审查的响应（取第一个响应）
        response = interrupt(request)
        logger.info(f"response: {response}")

        # 检查响应类型是否为“接受”（accept）
        if response["type"] == "accept":
            logger.info("接受工具调用,执行中...")
            logger.info(f"调用工具：{tool.name} 参数：{tool_input}")
            try:
                # 如果接受，直接调用原始工具并传入输入参数和配置
                tool_response = await tool.ainvoke(input=tool_input)
                logger.info(tool_response)
            except Exception as e:
                logger.error(f"调用工具失败: {e}")

        # 检查响应类型是否为“编辑”（edit）
        elif response["type"] == "edit":
            # 如果是编辑，更新工具输入参数为响应中提供的参数
            tool_input = response["args"]["args"]
            try:
                tool_response = await tool.ainvoke(input=tool_input)
                logger.info(tool_response)
            except Exception as e:
                logger.error(f"调用工具失败: {e}")

        # 检查响应类型是否为“拒绝”（reject）
        elif response["type"] == "reject":
            logger.info("工具调用被拒绝，等待用户输入...")
            # 直接将用户反馈作为工具的响应
            tool_response = "该工具被拒绝使用，请尝试其他方法或拒绝回答问题。"

        # 检查响应类型是否为“响应”（response）
        elif response["type"] == "response":
            # 如果是响应，直接将用户反馈作为工具的响应
            user_feedback = response["args"]
            tool_response = user_feedback

        else:
            raise ValueError(f"不支持的中断响应类型: {response['type']}")

        # 返回工具的响应结果
        return tool_response

    return call_tool_with_interrupt


async def get_tools():
    """
    获取工具
    """
    client = MultiServerMCPClient(
        # MCP Server配置
        mcp_server_configs
    )
    mcp_server_tools = await client.get_tools()
    # 为mcp server工具加入人工审核
    tools = [await add_human_in_the_loop(index) for index in mcp_server_tools]
    # 追加自定义工具并添加人工审核
    tools_lsit = [await add_human_in_the_loop(index) for index in review_tools]
    tools.extend(tools_lsit)
    # 追加自定义工具
    tools.extend(normal_tools)

    return tools


def read_md_file(file_path: str) -> str:
    """
    读取指定路径的md文件

    Args:
        file_path: md文件的路径

    Returns:
        文件内容字符串
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return f"文件 {file_path} 不存在"
    except Exception as e:
        return f"读取文件时出错: {str(e)}"


if __name__ == "__main__":
    import asyncio
    tools = asyncio.run(get_tools())
    for tool in tools:
        print(f"工具名称 (Name): {tool.name}")
        print(f"工具描述 (Description): {tool.description}")
        print(f"工具参数 (Args): {tool.args}")
        print("=" * 30)  # 打印分隔线

    # print(f"review_tools: {review_tools}")
    # print(f"normal_tools: {normal_tools}")
