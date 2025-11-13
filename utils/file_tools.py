

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
