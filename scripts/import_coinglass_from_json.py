"""
从本地 JSON 文件导入 CoinGlass 地址到 hl_address_list
只导入 remark 14/15/16 的地址

用法：
    python scripts/import_coinglass_from_json.py data/coinglass_g3_20260410_113305.json
"""
import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

REMARK_LABEL_MAP = {
    "14": "割肉侠",
    "15": "扛单狂人",
    "16": "爆仓达人",
}

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/import_coinglass_from_json.py <json文件路径>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        logger.error(f"文件不存在: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        addresses = json.load(f)
    logger.info(f"读取到 {len(addresses)} 条原始数据，来自: {json_path}")

    # 过滤 remark 14/15/16
    candidates = []
    for item in addresses:
        address = item.get("address", "").lower().strip()
        if not address:
            continue
        remark = str(item.get("remark", "")).strip()
        if remark not in REMARK_LABEL_MAP:
            continue
        candidates.append((address, REMARK_LABEL_MAP[remark]))

    logger.info(f"符合条件（remark 14/15/16）: {len(candidates)} 个地址")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()

        # 批量查重
        all_addrs = [a for a, _ in candidates]
        placeholders = ",".join(["%s"] * len(all_addrs))
        cursor.execute(f"SELECT address FROM hl_address_list WHERE address IN ({placeholders})", all_addrs)
        existing = {row[0] for row in cursor.fetchall()}
        logger.info(f"已存在: {len(existing)} 个，待插入: {len(candidates) - len(existing)} 个")

        # 批量插入（单条 SQL 多 VALUES，每批 500 条）
        new_rows = [
            (addr, label, "coinglass", now, now)
            for addr, label in candidates
            if addr not in existing
        ]
        BATCH_SIZE = 500
        for i in range(0, len(new_rows), BATCH_SIZE):
            batch = new_rows[i:i + BATCH_SIZE]
            placeholders2 = ",".join(["(%s,%s,%s,%s,%s,'active')"] * len(batch))
            flat_values = [v for row in batch for v in row]
            cursor.execute(
                f"INSERT IGNORE INTO hl_address_list (address,label,source,first_seen_at,last_updated_at,status) VALUES {placeholders2}",
                flat_values
            )
            logger.info(f"已写入第 {i // BATCH_SIZE + 1} 批，本批 {len(batch)} 条")

        conn.commit()
        logger.info(f"完成！新增: {len(new_rows)} | 跳过: {len(existing)}")

    except Exception as e:
        conn.rollback()
        logger.error(f"写入失败: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
