"""
从 HyperBot traders/discover 发现脆弱地址并写入 hl_address_list。

默认策略（可通过参数调整）：
  - 低胜率：winRate < 40
  - 高杠杆：avgLeverage > 10
  - 大亏损：totalPnl < -10000
  - 足够样本：positionCount > 20

鉴权环境变量（必填）：
  - HYPERBOT_ACCESS_KEY_ID
  - HYPERBOT_ACCESS_KEY_SECRET

可选环境变量：
  - HYPERBOT_BASE_URL（默认 https://openapi.hyperbot.network）

示例：
  python scripts/fetch_hyperbot_fragile_addresses.py
  python scripts/fetch_hyperbot_fragile_addresses.py --period 7 --pages 20 --win-rate-lt 35
"""
import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv

CST = timezone(timedelta(hours=8))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 与项目其余脚本保持一致：默认加载 config/.env
load_dotenv("config/.env")


def gen_signature(access_key_id: str, nonce: str, timestamp: str, secret: str, mode: str = "hex_b64") -> str:
    """
    生成 HmacSHA1 + Base64 签名。

    注意：HyperBot 官方示例是：
      1) HMAC-SHA1 得到摘要
      2) 摘要转 hex 字符串
      3) 对 hex 字符串做 base64
    """
    sign_text = f"AccessKeyId={access_key_id}&SignatureNonce={nonce}&Timestamp={timestamp}"
    digest = hmac.new(secret.encode("utf-8"), sign_text.encode("utf-8"), hashlib.sha1).digest()
    if mode == "hex_b64":
        hex_signature = digest.hex()
        return base64.b64encode(hex_signature.encode("utf-8")).decode("utf-8")
    if mode == "raw_b64":
        return base64.b64encode(digest).decode("utf-8")
    if mode == "hex_upper_b64":
        hex_signature = digest.hex().upper()
        return base64.b64encode(hex_signature.encode("utf-8")).decode("utf-8")
    raise ValueError(f"不支持的签名模式: {mode}")


def do_discover_request(
    base_url: str,
    access_key_id: str,
    access_key_secret: str,
    payload: Dict[str, Any],
    sign_mode: str,
) -> Dict[str, Any]:
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))
    signature = gen_signature(access_key_id, nonce, timestamp, access_key_secret, mode=sign_mode)
    query = urlencode(
        {
            "AccessKeyId": access_key_id,
            "SignatureNonce": nonce,
            "Timestamp": timestamp,
            "Signature": signature,
        }
    )
    url = f"{base_url}/api/upgrade/v2/hl/traders/discover?{query}"
    return post_json(url, payload)


def do_get_request(
    base_url: str,
    access_key_id: str,
    access_key_secret: str,
    path: str,
    extra_query: Dict[str, Any],
    sign_mode: str,
) -> Dict[str, Any]:
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))
    signature = gen_signature(access_key_id, nonce, timestamp, access_key_secret, mode=sign_mode)
    query_map = {
        "AccessKeyId": access_key_id,
        "SignatureNonce": nonce,
        "Timestamp": timestamp,
        "Signature": signature,
    }
    query_map.update(extra_query or {})
    query = urlencode(query_map)
    url = f"{base_url}{path}?{query}"
    req = Request(url=url, method="GET")
    with urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def post_json(url: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def build_label(args: argparse.Namespace) -> str:
    """
    方案B：中文可读标签，随参数动态变化。
    """
    parts = [
        f"period={args.period}",
        f"winRate<{args.win_rate_lt}",
        f"lev>{args.avg_leverage_gt}",
        f"pnl<{args.total_pnl_lt}",
        f"pos>{args.position_count_gt}",
    ]
    if args.avg_duration_min_lt is not None:
        parts.append(f"avgDurationMin<{args.avg_duration_min_lt}")
    if args.margin_used_gt is not None:
        parts.append(f"snapTotalMarginUsed>{args.margin_used_gt}")
    return "脆弱候选(" + ", ".join(parts) + ")"


def build_payload(args: argparse.Namespace, page_num: int, extra_filters: List[Dict[str, Any]]) -> Dict[str, Any]:
    filters = [
        {"field": "winRate", "op": "<", "val": args.win_rate_lt},
        {"field": "avgLeverage", "op": ">", "val": args.avg_leverage_gt},
        {"field": "positionCount", "op": ">", "val": args.position_count_gt},
    ]
    filters.extend(extra_filters)
    if args.avg_duration_min_lt is not None:
        filters.append({"field": "avgDurationMin", "op": "<", "val": args.avg_duration_min_lt})
    if args.margin_used_gt is not None:
        filters.append({"field": "snapTotalMarginUsed", "op": ">", "val": args.margin_used_gt})

    return {
        "pageNum": page_num,
        "pageSize": args.page_size,
        "period": args.period,
        "sort": {"field": args.sort_field, "dir": args.sort_dir},
        "filters": filters,
        "selects": [
            "address",
            "winRate",
            "avgLeverage",
            "totalPnl",
            "longRatio",
            "avgDurationMin",
            "positionCount",
            "snapTotalMarginUsed",
            "snapPerpValue",
        ],
        "loadPnls": False,
        "loadTags": args.load_tags,
    }


def build_default_pnl_shards(total_pnl_lt: float) -> List[tuple]:
    """
    构建默认 totalPnl 分片（从大亏到接近阈值），用于突破分页上限。
    例如 total_pnl_lt=-10000:
      (-1e12,-1000000), (-1000000,-500000), ..., (-20000,-10000)
    """
    threshold = total_pnl_lt
    if threshold >= 0:
        threshold = -10000

    base = abs(threshold)
    cuts = sorted(
        set(
            [
                -1_000_000_000_000.0,
                -100 * base,
                -50 * base,
                -20 * base,
                -10 * base,
                -5 * base,
                -2 * base,
                -1 * base,
            ]
        )
    )

    shards: List[tuple] = []
    for i in range(len(cuts) - 1):
        low = cuts[i]
        high = cuts[i + 1]
        if high <= threshold:
            shards.append((low, high))
    return shards


def fetch_pages_with_filters(
    args: argparse.Namespace,
    base_url: str,
    access_key_id: str,
    access_key_secret: str,
    extra_filters: List[Dict[str, Any]],
    shard_name: str,
    seen: set,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []
    max_pages = max(1, args.pages)

    for page_num in range(1, max_pages + 1):
        payload = build_payload(args, page_num, extra_filters)

        logger.info("请求 discover: %s page=%s", shard_name, page_num)
        resp = None
        last_err = None
        sign_modes = ["hex_b64", "raw_b64", "hex_upper_b64"]
        for idx, mode in enumerate(sign_modes):
            try:
                if idx > 0:
                    logger.warning("签名重试模式: %s", mode)
                resp = do_discover_request(
                    base_url=base_url,
                    access_key_id=access_key_id,
                    access_key_secret=access_key_secret,
                    payload=payload,
                    sign_mode=mode,
                )
                last_err = None
                break
            except HTTPError as e:
                text = e.read().decode("utf-8", errors="ignore")
                last_err = RuntimeError(f"HTTPError {e.code}: {text}")
                if "1010" in text and idx < len(sign_modes) - 1:
                    continue
                raise last_err from e
            except URLError as e:
                last_err = RuntimeError(f"URLError: {e}")
                raise last_err from e

        if resp is None and last_err:
            raise last_err

        code = str(resp.get("code", ""))
        if code != "0":
            msg = str(resp.get("msg", ""))
            if code == "1010":
                raise RuntimeError("discover 返回 1010（鉴权失败/无权限）。请确认 API Key 权限、IP 白名单与时间同步。")
            raise RuntimeError(f"discover 返回失败: code={code}, msg={msg}")

        data = resp.get("data") or {}
        rows = data.get("list") or []
        total = data.get("total")
        logger.info("%s 第 %s 页返回 %s 条，total=%s", shard_name, page_num, len(rows), total)

        if not rows:
            break

        for row in rows:
            addr = str(row.get("address", "")).strip().lower()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            rows_out.append(row)

        if len(rows) < args.page_size:
            break

    return rows_out


def fetch_fragile_addresses(args: argparse.Namespace) -> List[Dict[str, Any]]:
    # 主键名 + 兼容别名（避免已有环境变量命名差异导致脚本不可用）
    access_key_id = (
        os.getenv("HYPERBOT_ACCESS_KEY_ID", "").strip()
        or os.getenv("HYPERBOT_ACCESS_KEY", "").strip()
        or os.getenv("HYPERBOT_API_KEY", "").strip()
    )
    access_key_secret = (
        os.getenv("HYPERBOT_ACCESS_KEY_SECRET", "").strip()
        or os.getenv("HYPERBOT_SECRET_KEY", "").strip()
        or os.getenv("HYPERBOT_API_SECRET", "").strip()
    )
    base_url = os.getenv("HYPERBOT_BASE_URL", "https://openapi.hyperbot.network").rstrip("/")

    if not access_key_id or not access_key_secret:
        raise ValueError(
            "缺少 HyperBot 鉴权配置，请在 config/.env 设置 "
            "HYPERBOT_ACCESS_KEY_ID + HYPERBOT_ACCESS_KEY_SECRET（或兼容别名）"
        )

    all_rows: List[Dict[str, Any]] = []
    seen = set()

    # 方案1：按 totalPnl 区间切片，再分页抓取并去重
    shards = build_default_pnl_shards(args.total_pnl_lt)
    logger.info("启用 PnL 分片抓取，共 %s 个分片", len(shards))

    for low, high in shards:
        extra_filters = [
            {"field": "totalPnl", "op": ">", "val": low},
            {"field": "totalPnl", "op": "<", "val": high},
        ]
        shard_name = f"pnl({low:.0f},{high:.0f})"
        shard_rows = fetch_pages_with_filters(
            args=args,
            base_url=base_url,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            extra_filters=extra_filters,
            shard_name=shard_name,
            seen=seen,
        )
        logger.info("%s 新增去重地址: %s", shard_name, len(shard_rows))
        all_rows.extend(shard_rows)

    return all_rows


def resolve_auth_config() -> tuple[str, str, str]:
    access_key_id = (
        os.getenv("HYPERBOT_ACCESS_KEY_ID", "").strip()
        or os.getenv("HYPERBOT_ACCESS_KEY", "").strip()
        or os.getenv("HYPERBOT_API_KEY", "").strip()
    )
    access_key_secret = (
        os.getenv("HYPERBOT_ACCESS_KEY_SECRET", "").strip()
        or os.getenv("HYPERBOT_SECRET_KEY", "").strip()
        or os.getenv("HYPERBOT_API_SECRET", "").strip()
    )
    base_url = os.getenv("HYPERBOT_BASE_URL", "https://openapi.hyperbot.network").rstrip("/")
    if not access_key_id or not access_key_secret:
        raise ValueError(
            "缺少 HyperBot 鉴权配置，请在 config/.env 设置 "
            "HYPERBOT_ACCESS_KEY_ID + HYPERBOT_ACCESS_KEY_SECRET（或兼容别名）"
        )
    return access_key_id, access_key_secret, base_url


def auth_check(args: argparse.Namespace) -> None:
    access_key_id, access_key_secret, base_url = resolve_auth_config()
    sign_modes = ["hex_b64", "raw_b64", "hex_upper_b64"]

    logger.info("开始鉴权自检...")

    # 1) 全局接口：tickers
    tickers_ok = False
    for mode in sign_modes:
        try:
            resp = do_get_request(
                base_url=base_url,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                path="/api/upgrade/v2/hl/tickers",
                extra_query={},
                sign_mode=mode,
            )
            code = str(resp.get("code", ""))
            if code == "0":
                logger.info("✅ tickers 鉴权通过（mode=%s）", mode)
                tickers_ok = True
                break
            logger.warning("tickers 返回 code=%s, msg=%s（mode=%s）", code, resp.get("msg"), mode)
        except HTTPError as e:
            text = e.read().decode("utf-8", errors="ignore")
            logger.warning("tickers HTTPError %s（mode=%s）: %s", e.code, mode, text)
        except Exception as e:
            logger.warning("tickers 请求异常（mode=%s）: %s", mode, e)

    # 2) discover 最小请求：countOnly=true
    discover_ok = False
    discover_payload = {
        "pageNum": 1,
        "pageSize": min(args.page_size, 25),
        "period": args.period,
        "countOnly": True,
        "filters": [{"field": "totalPnl", "op": "<", "val": args.total_pnl_lt}],
    }
    for mode in sign_modes:
        try:
            resp = do_discover_request(
                base_url=base_url,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                payload=discover_payload,
                sign_mode=mode,
            )
            code = str(resp.get("code", ""))
            if code == "0":
                logger.info("✅ discover 鉴权通过（mode=%s）", mode)
                discover_ok = True
                break
            logger.warning("discover 返回 code=%s, msg=%s（mode=%s）", code, resp.get("msg"), mode)
        except HTTPError as e:
            text = e.read().decode("utf-8", errors="ignore")
            logger.warning("discover HTTPError %s（mode=%s）: %s", e.code, mode, text)
        except Exception as e:
            logger.warning("discover 请求异常（mode=%s）: %s", mode, e)

    if tickers_ok and discover_ok:
        logger.info("🎉 鉴权自检通过：可执行正式抓取。")
        return
    if tickers_ok and not discover_ok:
        logger.error("❌ 全局鉴权正常，但 discover 失败：大概率是该接口权限或白名单限制。")
        return
    logger.error("❌ 全局鉴权失败：请优先检查 Key/Secret、白名单和系统时间。")


def save_to_db(rows: List[Dict[str, Any]], source: str, label: str) -> Dict[str, int]:
    if not rows:
        return {"inserted": 0, "skipped": 0}

    now = datetime.now(CST).replace(tzinfo=None)
    addresses = [str(r.get("address", "")).strip().lower() for r in rows]
    addresses = [a for a in addresses if a]

    if not addresses:
        return {"inserted": 0, "skipped": 0}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        placeholders = ",".join(["%s"] * len(addresses))
        cursor.execute(f"SELECT address FROM hl_address_list WHERE address IN ({placeholders})", addresses)
        existing = {row[0] for row in cursor.fetchall()}

        new_rows = [(a, label, source, now, now) for a in addresses if a not in existing]
        if new_rows:
            cursor.executemany(
                """
                INSERT IGNORE INTO hl_address_list
                (address, label, source, first_seen_at, last_updated_at, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                """,
                new_rows,
            )
        conn.commit()
        return {"inserted": len(new_rows), "skipped": len(existing)}
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过 HyperBot discover 拉取脆弱地址并入库")
    parser.add_argument("--period", type=int, default=30, help="统计周期天数，默认30")
    parser.add_argument("--pages", type=int, default=20, help="每个分片最多抓取页数，默认20")
    parser.add_argument("--page-size", type=int, default=25, help="每页条数，默认25（接口上限25）")
    parser.add_argument("--sort-field", type=str, default="totalPnl", help="排序字段，默认 totalPnl")
    parser.add_argument("--sort-dir", type=str, default="asc", choices=["asc", "desc"], help="排序方向")

    parser.add_argument("--win-rate-lt", type=float, default=40, help="过滤：winRate < x")
    parser.add_argument("--avg-leverage-gt", type=float, default=10, help="过滤：avgLeverage > x")
    parser.add_argument("--total-pnl-lt", type=float, default=-10000, help="过滤：totalPnl < x")
    parser.add_argument("--position-count-gt", type=float, default=20, help="过滤：positionCount > x")
    parser.add_argument("--avg-duration-min-lt", type=float, default=None, help="可选过滤：avgDurationMin < x")
    parser.add_argument("--margin-used-gt", type=float, default=None, help="可选过滤：snapTotalMarginUsed > x")

    parser.add_argument("--load-tags", action="store_true", help="discover 请求中启用 loadTags=true")
    parser.add_argument("--source", type=str, default="hyperbot", help="写入 hl_address_list.source，默认 hyperbot")
    parser.add_argument("--dry-run", action="store_true", help="仅打印结果，不写数据库")
    parser.add_argument("--auth-check", action="store_true", help="仅做鉴权自检（tickers + discover），不抓取不入库")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.auth_check:
        auth_check(args)
        return
    label = build_label(args)
    logger.info("=" * 70)
    logger.info("HyperBot 脆弱地址发现")
    logger.info("source=%s", args.source)
    logger.info("label=%s", label)
    logger.info("=" * 70)

    rows = fetch_fragile_addresses(args)
    logger.info("去重后共发现地址: %s", len(rows))
    for item in rows[:5]:
        logger.info(
            "预览: %s | winRate=%s | lev=%s | pnl=%s | pos=%s",
            str(item.get("address", "")).lower(),
            item.get("winRate"),
            item.get("avgLeverage"),
            item.get("totalPnl"),
            item.get("positionCount"),
        )

    if args.dry_run:
        logger.info("dry-run 模式，不写库。")
        return

    result = save_to_db(rows, source=args.source, label=label)
    logger.info("入库完成：新增=%s，跳过=%s", result["inserted"], result["skipped"])


if __name__ == "__main__":
    main()
