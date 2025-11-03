import os
import dotenv

dotenv.load_dotenv()

# 模型配置
model_configs = {
    "qwen3": {
        "model": "qwen3-max",
        "base_url": os.getenv("DASHSCOPE_BASE_URL"),
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": os.getenv("DEEPSEEK_BASE_URL"),
        "api_key": os.getenv("DEEPSEEK_API_KEY"),
    },
    "qwen_embedding": {
        "model": "text-embedding-v3",
        "base_url": os.getenv("DASHSCOPE_BASE_URL"),
        "api_key": os.getenv("DASHSCOPE_API_KEY"),
    }
}

class ModelParameter:
    """模型参数"""
    DEFAULT_LLM_TYPE = "qwen3"
    DEFAULT_EMBEDDING_MODEL = "qwen_embedding"
    DEFAULT_TEMPERATURE = 0
    DEFAULT_TIMEOUT = 30  # 请求超时时间
    DEFAULT_MAX_RETRIES = 2  # 请求重试次数