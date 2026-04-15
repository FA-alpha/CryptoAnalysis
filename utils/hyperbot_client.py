"""
HyperBot API 客户端
- 统一处理鉴权（HmacSHA1 + Base64）
- 支持 GET / POST
"""

import hashlib
import hmac
import base64
import time
import uuid
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://openapi.hyperbot.network"


def _sign(secret_key: str, access_key: str, nonce: str, timestamp: str) -> str:
    """
    生成 HmacSHA1 + Base64 签名

    签名字符串格式：AccessKeyId + SignatureNonce + Timestamp
    """
    raw = f"{access_key}{nonce}{timestamp}"
    mac = hmac.new(secret_key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("utf-8")


def _auth_params(access_key: str, secret_key: str) -> dict:
    """生成鉴权参数"""
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))
    signature = _sign(secret_key, access_key, nonce, timestamp)
    return {
        "AccessKeyId": access_key,
        "SignatureNonce": nonce,
        "Timestamp": timestamp,
        "Signature": signature,
    }


class HyperbotClient:
    """HyperBot API 同步客户端"""

    def __init__(self, access_key: str, secret_key: str, timeout: int = 30):
        self.access_key = access_key
        self.secret_key = secret_key
        self.timeout = timeout

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """
        发起 GET 请求，鉴权参数作为 QueryString

        Args:
            path: 接口路径，如 /api/upgrade/v2/hl/whales/open-positions
            params: 业务参数（可选）

        Returns:
            API 返回的 data 字段
        """
        auth = _auth_params(self.access_key, self.secret_key)
        query = {**auth, **(params or {})}
        url = f"{BASE_URL}{path}"
        logger.debug(f"GET {url} params={list(query.keys())}")
        try:
            resp = httpx.get(url, params=query, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 200:
                raise ValueError(f"API error: code={result.get('code')} msg={result.get('msg')}")
            return result.get("data")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"GET 请求失败: {e}", exc_info=True)
            raise

    def post(self, path: str, body: Optional[dict] = None) -> dict:
        """
        发起 POST 请求，鉴权参数作为 QueryString，业务参数放 Body

        Args:
            path: 接口路径
            body: 请求体业务参数

        Returns:
            API 返回的 data 字段
        """
        auth = _auth_params(self.access_key, self.secret_key)
        url = f"{BASE_URL}{path}"
        logger.debug(f"POST {url} body={body}")
        try:
            resp = httpx.post(url, params=auth, json=body or {}, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 200:
                raise ValueError(f"API error: code={result.get('code')} msg={result.get('msg')}")
            return result.get("data")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"POST 请求失败: {e}", exc_info=True)
            raise
