import logging


from concurrent_log_handler import ConcurrentRotatingFileHandler

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chat_models import init_chat_model

from configs.configuration import ConfigLogFile
from configs.model_configs import model_configs, ModelParameter

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


class LLMInitializationError(Exception):
    """自定义异常类用于LLM初始化错误"""
    pass


def initialize_llm(
    chat_model_type: str = ModelParameter.DEFAULT_LLM_TYPE,
    embedding_model_type: str = ModelParameter.DEFAULT_EMBEDDING_MODEL,
    temperature: float = ModelParameter.DEFAULT_TEMPERATURE
):
    """
    初始化大模型
    Args:
        chat_model_type: 聊天模型类型,可选值为"qwen3", "deepseek"
        embedding_model_type: 嵌入模型类型,可选值为"text-embedding-v3"
        temperature: 温度
    Returns:
        chat_model: 聊天模型
        embedding_model: 嵌入模型
    """
    try:
        if chat_model_type not in model_configs:
            raise ValueError(
                f"不支持llm类型： {chat_model_type},可选值为：{list(model_configs.keys())}")

        chat_model_config = model_configs[chat_model_type]
        embedding_model_config = model_configs[embedding_model_type]

        embedding_model = DashScopeEmbeddings(
            model=embedding_model_config["model"],
            dashscope_api_key=embedding_model_config["api_key"]
        )

        if chat_model_type == "deepseek":
            chat_model = init_chat_model(
                model=chat_model_config["model"],
                api_key=chat_model_config["api_key"],
                base_url=chat_model_config["base_url"],
                timeout=ModelParameter.DEFAULT_TIMEOUT,
                max_retries=ModelParameter.DEFAULT_MAX_RETRIES,
                temperature=temperature,
            )
        else:
            chat_model = ChatOpenAI(
                model=chat_model_config["model"],
                api_key=chat_model_config["api_key"],
                base_url=chat_model_config["base_url"],
                timeout=ModelParameter.DEFAULT_TIMEOUT,
                max_retries=ModelParameter.DEFAULT_MAX_RETRIES,
                temperature=temperature,
            )
        logger.info(f"初始化大模型成功：{chat_model_type}")
        return chat_model, embedding_model
    except ValueError as ve:
        logger.error(f"chat model 配置错误：{str(ve)}")
        raise LLMInitializationError(f"chat model 配置错误：{str(ve)}")
    except Exception as e:
        logger.error(f"初始化大模型失败：{str(e)}")
        raise LLMInitializationError(f"初始化大模型失败：{str(e)}")


def get_llm(
    chat_model_type: str = ModelParameter.DEFAULT_LLM_TYPE,
    embedding_model_type: str = ModelParameter.DEFAULT_EMBEDDING_MODEL,
    temperature: float = ModelParameter.DEFAULT_TEMPERATURE
):
    """
    获取大模型实例封装函数，提供默认值和错误处理
    Args:
        chat_model_type: 聊天模型类型
        embedding_model_type: 嵌入模型类型
        temperature: 温度
    Returns:
        chat_model: 聊天模型
        embedding_model: 嵌入模型
    """
    try:
        return initialize_llm(chat_model_type, embedding_model_type, temperature)
    except LLMInitializationError as e:
        logger.warning(f"使用默认配置重试: {str(e)}")
        if chat_model_type != ModelParameter.DEFAULT_LLM_TYPE:
            return initialize_llm(
                chat_model_type=ModelParameter.DEFAULT_LLM_TYPE,
                embedding_model_type=ModelParameter.DEFAULT_EMBEDDING_MODEL,
                temperature=ModelParameter.DEFAULT_TEMPERATURE
            )
        print(f"获取大模型实例失败：{str(e)},使用默认模型")
        raise


if __name__ == "__main__":
    chat_model, embedding_model = get_llm(
        chat_model_type="deepseek", embedding_model_type="qwen_embedding")
    # 测试嵌入模型
    text_to_embed = "Hello, world!"
    print(f"Embedding text: '{text_to_embed}'")
    embedding = embedding_model.embed_query(text_to_embed)
    print(f"Embedding result (前5个维度): {embedding[:5]}...")
    print(f"Embedding 维度: {len(embedding)}")

    # 测试聊天模型
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你是谁"}
    ]
    response = chat_model.invoke(messages)
    print(response)
