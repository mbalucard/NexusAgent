import os
import dotenv

dotenv.load_dotenv()

mcp_server_configs = {
    "amap-maps": {
        "transport": "sse",
        "url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/sse",
        "headers": {
            "Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY')}"
        }
    }
}
