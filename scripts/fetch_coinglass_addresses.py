"""
从 CoinGlass 获取 Hyperliquid 地址列表
通过 Playwright 注入 JSON.parse hook 拦截页面解密后的明文数据，
触发翻页加载所有地址，并写入 hl_address_list 表

用法：
    python scripts/fetch_coinglass_addresses.py              # 默认 groupId=15
    python scripts/fetch_coinglass_addresses.py --group 3   # 指定 groupId
    python scripts/fetch_coinglass_addresses.py --pages 10  # 指定页数（每页20条）
"""
import sys
import os
import argparse
import logging
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))  # 北京时间
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from utils.db_utils import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

COINGLASS_URL = "https://www.coinglass.com/zh/hl/range/{group_id}"

REMARK_LABEL_MAP = {
    "14": "割肉侠",
    "15": "扛单狂人",
    "16": "爆仓达人",
}


def fetch_addresses_via_browser(group_id: int, total_pages: int = 5) -> List[Dict]:
    """
    通过 Playwright 注入 JSON.parse hook，拦截页面解密后的地址数据

    原理：
    - CoinGlass 响应数据经 AES 加密，密钥由动态参数生成
    - 解密后必然调用 JSON.parse，在此处拦截可直接拿到明文
    - 通过模拟点击分页按钮触发多页加载

    Args:
        group_id: CoinGlass 分组 ID
        total_pages: 获取页数（每页 20 条）

    Returns:
        地址信息列表
    """
    url = COINGLASS_URL.format(group_id=group_id)
    logger.info(f"启动浏览器，访问: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # 注入 hook：拦截 JSON.parse，捕获含 address 数组的解密结果
        page.add_init_script("""
        window.__captured_addresses = [];
        window.__captured_pages = new Set();

        const _origParse = JSON.parse;
        JSON.parse = function(text) {
            const result = _origParse(text);
            try {
                if (
                    result &&
                    result.list &&
                    Array.isArray(result.list) &&
                    result.list.length > 0 &&
                    result.list[0] &&
                    result.list[0].address
                ) {
                    // 用首个地址作为去重标识，避免同一页重复捕获
                    const pageKey = result.list[0].address;
                    if (!window.__captured_pages.has(pageKey)) {
                        window.__captured_pages.add(pageKey);
                        window.__captured_addresses.push(...result.list);
                    }
                }
            } catch(e) {}
            return result;
        };
        """)

        # 监听 console 日志（调试用）
        def on_console(msg):
            if "error" in msg.type.lower():
                logger.debug(f"[browser] {msg.text}")

        page.on("console", on_console)

        # 加载首页（会自动触发第1页数据请求）
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        current_count = page.evaluate("() => window.__captured_addresses.length")
        logger.info(f"首页加载完成，已捕获: {current_count} 个地址")

        # 翻页：找分页按钮，点击加载后续页
        if total_pages > 1:
            for target_page in range(2, total_pages + 1):
                try:
                    # 找 "下一页" 按钮（多种选择器兜底）
                    clicked = False
                    for selector in [
                        'li.ant-pagination-next:not(.ant-pagination-disabled)',
                        'button[aria-label="next page"]',
                        '.ant-pagination-next:not(.ant-pagination-disabled)',
                        '[class*="pagination"] [class*="next"]:not([class*="disabled"])',
                    ]:
                        btn = page.query_selector(selector)
                        if btn:
                            btn.click()
                            page.wait_for_timeout(2500)
                            clicked = True
                            break

                    if not clicked:
                        # 尝试直接点击页码数字
                        page_btn = page.query_selector(f'li[title="{target_page}"]')
                        if page_btn:
                            page_btn.click()
                            page.wait_for_timeout(2500)
                            clicked = True

                    if not clicked:
                        logger.warning(f"第 {target_page} 页：未找到翻页按钮，停止翻页")
                        break

                    new_count = page.evaluate("() => window.__captured_addresses.length")
                    logger.info(f"第 {target_page} 页加载完成，累计捕获: {new_count} 个地址")

                except Exception as e:
                    logger.warning(f"翻页到第 {target_page} 页失败: {e}")
                    break

        all_addresses = page.evaluate("() => window.__captured_addresses")
        browser.close()

    logger.info(f"共获取 {len(all_addresses)} 个地址")
    return all_addresses


def save_addresses_to_db(addresses: List[Dict], source: str = "coinglass") -> Dict[str, int]:
    """
    将地址保存到 hl_address_list 表（跳过已存在的地址）

    Args:
        addresses: 地址信息列表
        source: 来源标识

    Returns:
        {'inserted': int, 'skipped': int}
    """
    if not addresses:
        logger.warning("没有地址需要保存")
        return {"inserted": 0, "skipped": 0}

    conn = get_connection()
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    try:
        now = datetime.now(CST).replace(tzinfo=None)  # 北京时间，存为 naive datetime

        # 过滤出 remark 14/15/16 的地址
        candidates = []
        for item in addresses:
            address = item.get("address", "").lower().strip()
            if not address:
                continue
            remark = str(item.get("remark", "")).strip()
            if remark not in REMARK_LABEL_MAP:
                skipped += 1
                continue
            candidates.append((address, REMARK_LABEL_MAP[remark]))

        if not candidates:
            logger.warning("没有符合 remark 14/15/16 的地址")
            return {"inserted": 0, "skipped": skipped}

        # 批量查询已存在的地址
        all_addrs = [a for a, _ in candidates]
        placeholders = ",".join(["%s"] * len(all_addrs))
        cursor.execute(f"SELECT address FROM hl_address_list WHERE address IN ({placeholders})", all_addrs)
        existing = {row[0] for row in cursor.fetchall()}
        logger.info(f"已存在 {len(existing)} 个，待插入 {len(candidates) - len(existing)} 个")

        # 批量插入（每批 500 条）
        BATCH_SIZE = 500
        new_rows = [
            (addr, label, source, now, now)
            for addr, label in candidates
            if addr not in existing
        ]
        for i in range(0, len(new_rows), BATCH_SIZE):
            batch = new_rows[i:i + BATCH_SIZE]
            cursor.executemany("""
                INSERT IGNORE INTO hl_address_list
                (address, label, source, first_seen_at, last_updated_at, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
            """, batch)
            logger.info(f"已插入批次 {i // BATCH_SIZE + 1}，本批 {len(batch)} 条")

        conn.commit()
        inserted = len(new_rows)
        skipped += len(existing)
        logger.info(f"保存完成：新增 {inserted} 个，跳过 {skipped} 个")
        return {"inserted": inserted, "skipped": skipped}

    except Exception as e:
        conn.rollback()
        logger.error(f"保存失败: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="从 CoinGlass 获取 Hyperliquid 地址")
    parser.add_argument("--group", type=int, default=15, help="CoinGlass groupId（默认 15）")
    parser.add_argument("--pages", type=int, default=5, help="获取页数，每页 20 条（默认 5 页 = 100 个地址）")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CoinGlass 地址采集开始")
    logger.info(f"groupId={args.group}, pages={args.pages}（预计 {args.pages * 20} 个地址）")
    logger.info("=" * 60)

    addresses = fetch_addresses_via_browser(group_id=args.group, total_pages=args.pages)

    if not addresses:
        logger.error("未获取到任何地址，退出")
        sys.exit(1)

    # 打印前 5 个预览
    # 只预览 remark 14/15/16 的地址
    target = [a for a in addresses if str(a.get("remark", "")) in REMARK_LABEL_MAP]
    logger.info(f"\n=== 符合条件地址（remark 14/15/16）共 {len(target)} 个，预览前 5 个 ===")
    for item in target[:5]:
        addr = item.get("address", "?")
        margin = item.get("margin", 0)
        remark = str(item.get("remark", "?"))
        label = REMARK_LABEL_MAP.get(remark, "?")
        try:
            logger.info(f"  {addr} | margin: ${float(margin):,.0f} | remark: {remark}({label})")
        except Exception:
            logger.info(f"  {addr} | margin: {margin} | remark: {remark}({label})")

    # 保存原始数据到 JSON 文件
    import json
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"coinglass_g{args.group}_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(addresses, jf, ensure_ascii=False, indent=2)
    logger.info(f"原始数据已保存到: {json_path}")

    result = save_addresses_to_db(addresses, source="coinglass")

    logger.info("=" * 60)
    logger.info(f"完成！新增: {result['inserted']} | 跳过: {result['skipped']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
