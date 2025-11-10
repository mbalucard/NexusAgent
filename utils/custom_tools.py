from langchain.tools import tool


@tool("book_hotel", description="酒店预定工具")
async def book_hotel(hotel_name: str):
    """
    支持酒店预定的工具

    Args:
        hotel_name: 酒店名称
    Returns:
        工具的调用结果
    """
    return f"成功预定了在{hotel_name}的住宿。"


@tool("book_flight_ticket", description="机票预定工具")
async def book_flight_ticket(place_of_departure: str, destination: str):
    """
    支持机票预定的工具

    Args:
        place_of_departure: 出发地
        destination: 目的地

    Returns:
        工具的调用结果
    """
    return f"成功预定了从{place_of_departure}到{destination}的机票。"


@tool("multiply", description="计算两个数的乘积的工具")
async def multiply(a: float, b: float) -> float:
    """
    支持计算两个数的乘积的工具

    Args:
        a: 参数1
        b: 参数2

    Returns:
        工具的调用结果
    """
    result = a * b
    return f"{a}乘以{b}等于{result}。"


@tool("add", description="计算两个数的和的工具")
async def add(a: float, b: float) -> float:
    """
    支持计算两个数的和的工具

    Args:
        a: 参数1
        b: 参数2

    Returns:
        工具的调用结果
    """
    result = a + b
    return f"{a}加{b}等于{result}。"


@tool("subtract", description="计算两个数的差的工具")
async def subtract(a: float, b: float) -> float:
    """
    支持计算两个数的差的工具

    Args:
        a: 参数1
        b: 参数2

    Returns:
        工具的调用结果
    """
    result = a - b
    return f"{a}减{b}等于{result}。"

# 需要人工审核的工具列表
review_tools = [book_hotel, book_flight_ticket]
# 不需要人工审核的工具列表
normal_tools = [multiply, add, subtract]

if __name__ == "__main__":
    print(f"review_tools: {review_tools}")
    print(f"normal_tools: {normal_tools}")
