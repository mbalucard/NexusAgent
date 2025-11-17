"""
RSA加密工具类 - Python实现
对应 TypeScript 版本的 rsa.ts
"""
import json
import base64
import os
import dotenv

from typing import Optional, List, Union, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

dotenv.load_dotenv()


class RSAUtil:
    """RSA加密工具类 - 单例模式"""

    # 默认公钥
    DEFAULT_PUBLIC_KEY = os.getenv("DEFAULT_RSA_PUBLIC_KEY")

    _instance: Optional['RSAUtil'] = None
    _public_key_obj: Optional[rsa.RSAPublicKey] = None

    def __init__(self, public_key: Optional[str] = None):
        """私有构造函数，使用 getInstance 获取实例"""
        if RSAUtil._instance is not None:
            raise RuntimeError("请使用 getInstance() 方法获取实例")

        self._public_key_str = public_key or RSAUtil.DEFAULT_PUBLIC_KEY
        self._load_public_key(self._public_key_str)

    def _load_public_key(self, public_key_str: str) -> None:
        """加载公钥"""
        try:
            # 将Base64编码的公钥转换为PEM格式
            # JSEncrypt使用的公钥是Base64编码的DER格式
            public_key_der = base64.b64decode(public_key_str)

            # 从DER格式加载公钥
            self._public_key_obj = serialization.load_der_public_key(
                public_key_der,
                backend=default_backend()
            )
        except Exception as e:
            raise ValueError(f"公钥加载失败: {e}")

    @classmethod
    def get_instance(cls, public_key: Optional[str] = None) -> 'RSAUtil':
        """
        获取单例实例
        :param public_key: 可选的公钥，不传则使用默认公钥
        :return: RSAUtil实例
        """
        if cls._instance is None:
            cls._instance = cls(public_key)
        elif public_key and public_key != cls._instance._public_key_str:
            # 如果传入了新的公钥，更新实例
            cls._instance._public_key_str = public_key
            cls._instance._load_public_key(public_key)

        return cls._instance

    def encrypt_text(self, text: str) -> Optional[str]:
        """
        加密字符串
        :param text: 要加密的文本
        :return: Base64编码的加密字符串，失败返回None
        """
        try:
            if not text:
                print('警告: RSA加密：输入文本为空')
                return None

            if self._public_key_obj is None:
                print('错误: 公钥未加载')
                return None

            # 使用PKCS1v15填充方式加密（与JSEncrypt默认行为兼容）
            encrypted = self._public_key_obj.encrypt(
                text.encode('utf-8'),
                padding.PKCS1v15()
            )

            # 返回Base64编码的加密结果
            return base64.b64encode(encrypted).decode('utf-8')

        except Exception as e:
            print(f'RSA加密异常：{e}')
            return None

    def encrypt_object(self, obj: Any) -> Optional[str]:
        """
        加密对象（先JSON序列化再加密）
        :param obj: 要加密的对象
        :return: Base64编码的加密字符串，失败返回None
        """
        try:
            json_string = json.dumps(obj, ensure_ascii=False)
            return self.encrypt_text(json_string)
        except Exception as e:
            print(f'RSA对象加密异常：{e}')
            return None

    def encrypt_texts(self, texts: List[str]) -> List[Optional[str]]:
        """
        批量加密字符串数组
        :param texts: 要加密的文本数组
        :return: 加密后的字符串数组，失败的项为None
        """
        return [self.encrypt_text(text) for text in texts]

    def update_public_key(self, new_public_key: str) -> None:
        """
        更新公钥
        :param new_public_key: 新的公钥
        """
        self._public_key_str = new_public_key
        self._load_public_key(new_public_key)

    def get_public_key(self) -> str:
        """
        获取当前公钥
        :return: 当前使用的公钥
        """
        return self._public_key_str

    @staticmethod
    def validate_public_key(public_key: str) -> bool:
        """
        验证公钥是否有效
        :param public_key: 要验证的公钥
        :return: 是否有效
        """
        try:
            test_util = RSAUtil(public_key)
            test_result = test_util.encrypt_text('test')
            return test_result is not None
        except Exception as e:
            print(f'公钥验证失败：{e}')
            return False


def rsa_encrypt(text: str, public_key: Optional[str] = None) -> Optional[str]:
    """
    便捷的RSA加密函数
    :param text: 要加密的文本
    :param public_key: 可选的公钥，不传则使用默认公钥
    :return: Base64编码的加密字符串，失败返回None
    """
    rsa = RSAUtil.get_instance(public_key)
    return rsa.encrypt_text(text)


def rsa_encrypt_object(obj: Any, public_key: Optional[str] = None) -> Optional[str]:
    """
    便捷的RSA对象加密函数
    :param obj: 要加密的对象
    :param public_key: 可选的公钥，不传则使用默认公钥
    :return: Base64编码的加密字符串，失败返回None
    """
    rsa = RSAUtil.get_instance(public_key)
    return rsa.encrypt_object(obj)


def rsa_encrypt_texts(texts: List[str], public_key: Optional[str] = None) -> List[Optional[str]]:
    """
    便捷的批量RSA加密函数
    :param texts: 要加密的文本数组
    :param public_key: 可选的公钥，不传则使用默认公钥
    :return: 加密后的字符串数组，失败的项为None
    """
    rsa = RSAUtil.get_instance(public_key)
    return rsa.encrypt_texts(texts)


# 导出默认实例
default_instance = RSAUtil.get_instance()


if __name__ == '__main__':
    # 测试示例
    print("=== RSA加密工具测试 ===\n")

    # 测试1: 加密文本
    test_text = "123456"
    encrypted = rsa_encrypt(test_text)
    print(f"原文: {test_text}")
    print(f"加密后: {encrypted}\n")

    # 测试2: 加密对象
    test_obj = {"username": "admin", "password": "123456"}
    encrypted_obj = rsa_encrypt_object(test_obj)
    print(f"对象: {test_obj}")
    print(f"加密后: {encrypted_obj}\n")

    # 测试3: 批量加密
    test_texts = ["text1", "text2", "text3"]
    encrypted_texts = rsa_encrypt_texts(test_texts)
    print(f"批量文本: {test_texts}")
    print(f"加密后: {encrypted_texts}\n")

    # 测试4: 公钥验证
    is_valid = RSAUtil.validate_public_key(RSAUtil.DEFAULT_PUBLIC_KEY)
    print(f"公钥验证: {is_valid}")
