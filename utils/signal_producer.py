"""
信号生产者 — 供外部信号生成服务调用

独立文件，不依赖项目内其他模块，可直接复制使用。
使用前修改下方 REDIS_CONNECTION 配置。

用法：
    from signal_producer import send_signal
    send_signal(strategy_id="11", symbol="BTC/USDT:USDT", signal_type="entry_long",
                data={"price": "95000", "comment": "MACD crossover"})
"""
import logging
import time
import traceback
import uuid
import json

import redis

# ==================== 配置 ====================
REDIS_CONNECTION = {
    'host': 'fa-hyperliquid-rvppuf.serverless.usw1.cache.amazonaws.com',
    'port': 6379,
    'password': '',
    'db': 0,
}
# =============================================

SIGNAL_STREAM = 'fa:signal'

_logger = logging.getLogger('SignalProducer')

# 全局复用客户端
_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_CONNECTION['host'],
            port=REDIS_CONNECTION['port'],
            password=REDIS_CONNECTION.get('password', ''),
            db=REDIS_CONNECTION.get('db', 0),
            decode_responses=True,
            ssl=True,
            ssl_cert_reqs='none',
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


def send_signal(
    strategy_id: str,
    symbol: str,
    signal_type: str,
    signal_id: str | None = None,
    data: dict | None = None,
) -> str | None:
    """
    发送信号到 Redis Stream。

    :param strategy_id: 目标策略 ID
    :param symbol: 交易对，如 "BTC/USDT:USDT"
    :param signal_type: 信号类型，如 "entry_long", "exit_long"
    :param signal_id: 可选，用于去重/追踪，不传则自动生成 UUID
    :param data: 自定义信号数据，统一序列化到 Redis 消息体的 `data` 字段（JSON 字符串）
    :return: Redis 消息 ID，Redis 不可用时返回 None
    """
    client = _get_client()

    try:
        client.ping()
    except (redis.ConnectionError, redis.TimeoutError):
        _logger.warning("Redis not available, signal not sent")
        return None

    timestamp = int(time.time() * 1000)
    if signal_id is None:
        signal_id = str(uuid.uuid4())

    fields = {
        'strategy_id': strategy_id,
        'symbol': symbol,
        'signal_type': signal_type,
        'timestamp': timestamp,
        'signal_id': signal_id,
    }
    if data:
        # 与执行层 Signal.dataclass 对齐：
        # - 只在顶层放 strategy_id/symbol/signal_type/signal_id/timestamp
        # - 其他自定义字段统一放到 data 字段（JSON 字符串）
        fields["data"] = json.dumps({k: str(v) for k, v in data.items()}, ensure_ascii=False)

    try:
        message_id = client.xadd(SIGNAL_STREAM, fields)
        _logger.info(f"signal sent: {message_id} strategy_id={strategy_id} symbol={symbol} signal_type={signal_type}")
        return message_id
    except Exception:
        _logger.error(f"failed to send signal: {traceback.format_exc()}")
        return None
