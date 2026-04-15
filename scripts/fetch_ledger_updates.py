import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Add project root to sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Assume these modules exist and are correctly configured in your project
try:
    from utils.db_utils import get_connection
except ImportError as e:
    logging.error(
        "Failed to import necessary modules: %s. Ensure utils/db_utils.py exists.",
        e,
    )
    sys.exit(1)

logger = logging.getLogger(__name__)

HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz/info"


def get_all_active_addresses() -> List[str]:
    """
    按 fetch_address_fills_incremental.py 的方式，
    从 hl_address_list 获取所有 active 状态地址。
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT address FROM hl_address_list
            WHERE status = 'active'
            ORDER BY address
            """
        )
        rows = cursor.fetchall()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error("获取 active 地址失败: %s", e, exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


class DeltaData(BaseModel):
    type: Optional[str] = None
    user: Optional[str] = None
    destination: Optional[str] = None
    sourceDex: Optional[str] = None
    destinationDex: Optional[str] = None
    token: Optional[str] = None
    amount: Optional[str] = None
    usdcValue: Optional[str] = None
    fee: Optional[str] = None
    nativeTokenFee: Optional[str] = None
    nonce: Optional[int] = None
    usdc: Optional[str] = None
    feeToken: Optional[str] = None
    toPerp: Optional[bool] = None
    isDeposit: Optional[bool] = None
    operation: Optional[str] = None
    requestedUsd: Optional[str] = None
    netWithdrawnUsd: Optional[str] = None
    commission: Optional[str] = None
    closingCost: Optional[str] = None
    basis: Optional[str] = None
    vault: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ApiLedgerUpdate(BaseModel):
    time: int
    hash: str
    type: Optional[str] = None
    delta: DeltaData


class LedgerUpdatePydantic(BaseModel):
    address: str
    time: int
    hash: str
    type: str
    sender_address: Optional[str] = None
    destination_address: Optional[str] = None
    source_dex: Optional[str] = None
    destination_dex: Optional[str] = None
    token: Optional[str] = None
    amount: Optional[Decimal] = None
    usdc_value: Optional[Decimal] = None
    fee: Optional[Decimal] = None
    native_token_fee: Optional[Decimal] = None
    fee_token: Optional[str] = None
    usdc_amount: Optional[Decimal] = None
    withdraw_fee: Optional[Decimal] = None
    to_perp: Optional[bool] = None
    operation: Optional[str] = None
    is_deposit: Optional[bool] = None
    requested_usd: Optional[Decimal] = None
    net_withdrawn_usd: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    closing_cost: Optional[Decimal] = None
    basis: Optional[Decimal] = None
    vault_address: Optional[str] = None
    nonce: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


async def parse_decimal_string(
    value: Optional[str],
) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(value)
    except Exception:
        logger.warning("Could not parse '%s' as Decimal.", value)
        return None


async def normalize_api_data(
    api_update: ApiLedgerUpdate,
    monitored_address: str,
) -> LedgerUpdatePydantic:
    raw_event_type = (api_update.delta.type or api_update.type or "unknown").strip()
    lowered_event_type = raw_event_type.lower()
    if lowered_event_type in {"withdraw", "withdrawal"}:
        event_type = "withdraw"
    elif lowered_event_type == "deposit":
        event_type = "deposit"
    elif lowered_event_type == "send":
        event_type = "send"
    elif lowered_event_type == "accountclasstransfer":
        event_type = "accountClassTransfer"
    else:
        event_type = raw_event_type
    normalized = LedgerUpdatePydantic(
        address=monitored_address,
        time=api_update.time,
        hash=api_update.hash,
        type=event_type,
        nonce=api_update.delta.nonce,
    )
    delta = api_update.delta

    if event_type == "send":
        normalized.sender_address = delta.user
        normalized.destination_address = delta.destination
        normalized.source_dex = delta.sourceDex
        normalized.destination_dex = delta.destinationDex
        normalized.token = delta.token
        normalized.amount = await parse_decimal_string(delta.amount)
        normalized.usdc_value = await parse_decimal_string(delta.usdcValue)
        # 兼容分析口径：仅 send 且 token=USDC 时写入 usdc_amount
        if (delta.token or "").upper() == "USDC":
            # 优先使用 usdcValue，缺失时回退 amount
            normalized.usdc_amount = normalized.usdc_value or normalized.amount
        normalized.fee = await parse_decimal_string(delta.fee)
        normalized.native_token_fee = await parse_decimal_string(delta.nativeTokenFee)
        normalized.fee_token = delta.feeToken
    elif event_type == "withdraw":
        normalized.usdc_amount = await parse_decimal_string(delta.usdc)
        normalized.withdraw_fee = await parse_decimal_string(delta.fee)
    elif event_type == "deposit":
        normalized.usdc_amount = await parse_decimal_string(delta.usdc)
    elif event_type == "accountClassTransfer":
        normalized.usdc_amount = await parse_decimal_string(delta.usdc)
        normalized.to_perp = delta.toPerp
    elif event_type == "spotTransfer":
        normalized.sender_address = delta.user
        normalized.destination_address = delta.destination
        normalized.source_dex = delta.sourceDex
        normalized.destination_dex = delta.destinationDex
        normalized.token = delta.token
        normalized.amount = await parse_decimal_string(delta.amount)
        normalized.usdc_value = await parse_decimal_string(delta.usdcValue)
        if (delta.token or "").upper() == "USDC":
            normalized.usdc_amount = normalized.usdc_value or normalized.amount
        normalized.fee = await parse_decimal_string(delta.fee)
        normalized.native_token_fee = await parse_decimal_string(delta.nativeTokenFee)
        normalized.fee_token = delta.feeToken
    elif event_type in {"vaultDeposit", "vaultCreate", "vaultDistribution", "vaultLeaderCommission"}:
        # 统一保留 vault 相关语义字段，便于后续净流/费用拆分分析
        normalized.vault_address = delta.vault
        normalized.operation = delta.operation
        normalized.token = delta.token or "USDC"
        normalized.amount = await parse_decimal_string(delta.amount)
        normalized.usdc_value = await parse_decimal_string(delta.usdcValue)
        normalized.usdc_amount = await parse_decimal_string(delta.usdc)
        if normalized.usdc_amount is None:
            normalized.usdc_amount = normalized.usdc_value or normalized.amount
        normalized.commission = await parse_decimal_string(delta.commission)
        normalized.closing_cost = await parse_decimal_string(delta.closingCost)
        normalized.basis = await parse_decimal_string(delta.basis)
    elif event_type == "vaultWithdraw":
        # 优先净到账金额，其次退化为请求金额，并保留两者明细
        normalized.vault_address = delta.vault
        normalized.operation = delta.operation
        normalized.is_deposit = delta.isDeposit
        normalized.token = delta.token or "USDC"
        normalized.requested_usd = await parse_decimal_string(delta.requestedUsd)
        normalized.net_withdrawn_usd = await parse_decimal_string(delta.netWithdrawnUsd)
        normalized.usdc_amount = normalized.net_withdrawn_usd or normalized.requested_usd
        normalized.sender_address = delta.user
    elif event_type in {"borrowLend", "cStakingTransfer", "accountActivationGas"}:
        # 统一记录 token/amount，便于后续分析
        normalized.token = delta.token
        normalized.amount = await parse_decimal_string(delta.amount)
        normalized.fee = await parse_decimal_string(delta.fee)
        normalized.native_token_fee = await parse_decimal_string(delta.nativeTokenFee)
        normalized.fee_token = delta.feeToken

        # borrowLend 仅在 USDC 时映射到 usdc_amount
        if event_type == "borrowLend" and (delta.token or "").upper() == "USDC":
            normalized.usdc_amount = normalized.amount

        # cStakingTransfer 不等于 USDC 资金流，保留 token/amount 即可
        # accountActivationGas 也是 token 扣费事件，保留 token/amount 即可
    return normalized


async def fetch_ledger_updates_paginated(
    user_address: str,
    start_time_ms: Optional[int] = None,
    end_time_ms: Optional[int] = None,
    limit: int = 1000,
    client: Optional[httpx.AsyncClient] = None,
):
    url = HYPERLIQUID_API_URL
    all_updates: List[LedgerUpdatePydantic] = []
    query_start_time = start_time_ms
    logger.info(
        "Fetching ledger updates for %s from %s to %s",
        user_address,
        query_start_time,
        end_time_ms if end_time_ms else "now",
    )

    try:
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)

        while True:
            payload = {"type": "userNonFundingLedgerUpdates", "user": user_address}
            if query_start_time:
                payload["startTime"] = query_start_time
            if end_time_ms:
                payload["endTime"] = end_time_ms
            payload["limit"] = limit

            logger.debug("Querying ledger updates with payload: %s", payload)
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list) or not data:
                logger.info("Received empty or invalid data, stopping fetch.")
                break

            batch_updates: List[LedgerUpdatePydantic] = []
            earliest_time_in_batch = float("inf")

            for item in data:
                try:
                    api_update = ApiLedgerUpdate(**item)
                    normalized_update = await normalize_api_data(api_update, user_address)
                    batch_updates.append(normalized_update)
                    earliest_time_in_batch = min(
                        earliest_time_in_batch,
                        normalized_update.time,
                    )
                except ValidationError as e:
                    logger.warning("Skipping invalid API item: %s. Error: %s", item, e)
                except Exception as e:
                    logger.error(
                        "Error processing item %s: %s",
                        item.get("hash"),
                        e,
                        exc_info=True,
                    )

            if batch_updates:
                all_updates.extend(batch_updates)
                logger.info(
                    "Fetched %s updates. Total now: %s",
                    len(batch_updates),
                    len(all_updates),
                )

                if query_start_time is not None and earliest_time_in_batch < query_start_time:
                    query_start_time = earliest_time_in_batch - 1
                    logger.debug("Adjusting next query start time to: %s", query_start_time)
                    await asyncio.sleep(0.1)
                else:
                    logger.info(
                        "Reached end of available data or initial query range. "
                        "Stopping fetch."
                    )
                    break
            else:
                logger.info("No valid updates processed in this batch. Stopping fetch.")
                break

            if len(all_updates) >= 5000:
                logger.warning(
                    "Reached 5000 updates limit, stopping fetch to prevent excessive "
                    "data retrieval. Adjust script if more is needed."
                )
                break

    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error fetching ledger updates: %s - %s",
            e.response.status_code,
            e.response.text,
        )
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 10))
            logger.warning("Rate limited. Retrying after %s seconds.", retry_after)
            await asyncio.sleep(retry_after)
        return []
    except httpx.RequestError as e:
        logger.error("Request error fetching ledger updates: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error during fetch: %s", e, exc_info=True)
        return []
    finally:
        if client:
            await client.aclose()
    return all_updates


async def save_ledger_updates_to_db(updates: List[LedgerUpdatePydantic]) -> int:
    if not updates:
        logger.info("No updates to save to DB.")
        return 0
    logger.info("Attempting to save %s updates to database.", len(updates))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'hl_ledger_updates'
            """
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
        if not existing_columns:
            logger.error("Table hl_ledger_updates not found or has no readable columns.")
            return 0

        # 逻辑字段 -> 可选数据库列（按优先级）
        # 优先兼容当前库结构(usdc_amount)，其次兼容旧结构(withdraw/deposit/account_class_transfer)
        logical_column_candidates = [
            ("address", ["address"]),
            ("time", ["time"]),
            ("hash", ["hash"]),
            ("type", ["type"]),
            ("sender_address", ["sender_address"]),
            ("destination_address", ["destination_address"]),
            ("source_dex", ["source_dex"]),
            ("destination_dex", ["destination_dex"]),
            ("token", ["token"]),
            ("amount", ["amount"]),
            ("usdc_value", ["usdc_value"]),
            ("fee", ["fee"]),
            ("native_token_fee", ["native_token_fee"]),
            ("fee_token", ["fee_token"]),
            ("usdc_amount", ["usdc_amount"]),
            ("withdraw_fee", ["withdraw_fee"]),
            ("to_perp", ["to_perp"]),
            ("operation", ["operation"]),
            ("is_deposit", ["is_deposit"]),
            ("requested_usd", ["requested_usd"]),
            ("net_withdrawn_usd", ["net_withdrawn_usd"]),
            ("commission", ["commission"]),
            ("closing_cost", ["closing_cost"]),
            ("basis", ["basis"]),
            ("vault_address", ["vault_address", "vault"]),
            ("nonce", ["nonce"]),
        ]

        # 为旧表额外支持这3列（如果存在就写）
        legacy_type_amount_columns = {
            "withdraw_usdc": "withdraw",
            "deposit_usdc": "deposit",
            "account_class_transfer_usdc": "accountClassTransfer",
        }

        selected_columns = {}
        for logical_name, candidates in logical_column_candidates:
            for column_name in candidates:
                if column_name in existing_columns:
                    selected_columns[logical_name] = column_name
                    break

        required_logical = {"address", "time", "hash", "type"}
        if not required_logical.issubset(set(selected_columns.keys())):
            logger.error(
                "hl_ledger_updates missing required columns. Required logical columns: %s, existing table columns: %s",
                sorted(required_logical),
                sorted(existing_columns),
            )
            return 0

        insert_columns: List[str] = []
        value_getters = []

        for logical_name in [
            "address",
            "time",
            "hash",
            "type",
            "sender_address",
            "destination_address",
            "source_dex",
            "destination_dex",
            "token",
            "amount",
            "usdc_value",
            "fee",
            "native_token_fee",
            "fee_token",
            "usdc_amount",
            "withdraw_fee",
            "to_perp",
            "operation",
            "is_deposit",
            "requested_usd",
            "net_withdrawn_usd",
            "commission",
            "closing_cost",
            "basis",
            "vault_address",
            "nonce",
        ]:
            col = selected_columns.get(logical_name)
            if not col:
                continue
            insert_columns.append(col)
            value_getters.append(lambda u, attr=logical_name: getattr(u, attr))

        for legacy_col, match_type in legacy_type_amount_columns.items():
            if legacy_col in existing_columns:
                insert_columns.append(legacy_col)
                value_getters.append(
                    lambda u, t=match_type: u.usdc_amount if u.type == t else None
                )

        values = [tuple(getter(update) for getter in value_getters) for update in updates]

        if not values:
            logger.info("No valid values created from updates.")
            return 0

        placeholders = ", ".join(["%s"] * len(insert_columns))
        column_sql = ", ".join(insert_columns)
        updatable_columns = [c for c in insert_columns if c not in {"address", "time", "hash"}]
        update_sql = ", ".join([f"{c} = VALUES({c})" for c in updatable_columns])
        sql = f"""
            INSERT INTO hl_ledger_updates ({column_sql})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_sql}
        """

        cursor.executemany(sql, values)
        conn.commit()
        saved_count = len(values)
        logger.info("Successfully saved %s ledger updates to database.", saved_count)
        return saved_count
    except Exception as e:
        conn.rollback()
        logger.error("Error saving ledger updates to database: %s", e, exc_info=True)
        return 0
    finally:
        cursor.close()
        conn.close()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    addresses_to_monitor = []

    # 按 fetch_address_fills_incremental.py 的 SQL 方式获取 active 地址
    try:
        addresses_to_monitor = get_all_active_addresses()
        if not addresses_to_monitor:
            logger.warning("No active addresses found in hl_address_list, nothing to process.")
            return
        else:
            logger.info("Found %s active addresses to monitor.", len(addresses_to_monitor))
    except Exception as e:
        logger.error(f"Error retrieving active addresses from DB: {e}", exc_info=True)
        return

    delay_seconds = 0.5

    for i, user_address in enumerate(addresses_to_monitor):
        logger.info(
            "--- Processing address %s/%s: %s ---",
            i + 1,
            len(addresses_to_monitor),
            user_address,
        )

        fetch_start_time = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(time) FROM hl_ledger_updates
                WHERE address = %s
                """,
                (user_address,),
            )
            result = cursor.fetchone()
            latest_db_time = result[0] if result else None

            if latest_db_time:
                fetch_start_time = latest_db_time - 1
                logger.info(
                    "Latest DB time for %s: %s. Fetching from: %s",
                    user_address,
                    latest_db_time,
                    fetch_start_time,
                )
            else:
                fetch_start_time = int(
                    (datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000
                )
                logger.info(
                    "No DB record for %s. Fetching last 7 days starting from: %s",
                    user_address,
                    fetch_start_time,
                )
        except Exception as e:
            logger.error(
                "Error checking DB for %s: %s. Using default 7-day fetch.",
                user_address,
                e,
                exc_info=True,
            )
            fetch_start_time = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp() * 1000)
        finally:
            if "cursor" in locals():
                cursor.close()
            if "conn" in locals():
                conn.close()

        updates = await fetch_ledger_updates_paginated(
            user_address,
            start_time_ms=fetch_start_time,
        )

        if updates:
            saved_count = await save_ledger_updates_to_db(updates)
            logger.info(f"Address {user_address}: Saved {saved_count} ledger updates.")
        else:
            logger.info(f"Address {user_address}: No new or valid ledger updates to save.")
            
        if i < len(addresses_to_monitor) - 1:
            await asyncio.sleep(delay_seconds)

    logger.info("--- Script finished processing all addresses ---")


if __name__ == "__main__":
    # Ensure hl_ledger_updates table exists with required columns.
    try:
        # Use asyncio.run to execute the main async function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user.")
    except Exception as e:
        logger.error(f"An unhandled error occurred during execution: {e}", exc_info=True)
