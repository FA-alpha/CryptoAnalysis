"""
Hyperliquid API 数据采集模块
"""

import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd


class HyperliquidClient:
    """Hyperliquid API 客户端"""
    
    def __init__(self):
        self.base_url = "https://api.hyperliquid.xyz"
    
    async def _post(self, endpoint: str, payload: Dict) -> Dict:
        """发送 POST 请求"""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"API Error: {resp.status}")
                return await resp.json()
    
    async def get_meta(self) -> Dict:
        """获取市场元数据（所有交易对信息）"""
        return await self._post("/info", {"type": "metaAndAssetCtxs"})
    
    async def get_all_mids(self) -> Dict[str, float]:
        """获取所有币种中间价"""
        data = await self._post("/info", {"type": "allMids"})
        return {k: float(v) for k, v in data.items()}
    
    async def get_user_state(self, address: str) -> Dict:
        """
        获取用户账户状态
        
        Args:
            address: 用户地址 (0x...)
        
        Returns:
            包含 marginSummary, assetPositions 等
        """
        return await self._post("/info", {
            "type": "clearinghouseState",
            "user": address
        })
    
    async def get_user_fills(
        self, 
        address: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取用户成交记录
        
        Args:
            address: 用户地址
            limit: 返回数量（最多2000）
        """
        return await self._post("/info", {
            "type": "userFills",
            "user": address
        })
    
    async def get_user_fills_by_time(
        self,
        address: str,
        start_time: int,
        end_time: int = None
    ) -> List[Dict]:
        """
        按时间范围获取用户成交记录
        
        Args:
            address: 用户地址
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）
        """
        payload = {
            "type": "userFillsByTime",
            "user": address,
            "startTime": start_time
        }
        if end_time:
            payload["endTime"] = end_time
        
        return await self._post("/info", payload)
    
    async def get_l2_book(self, coin: str, n_levels: int = 20) -> Dict:
        """获取订单簿"""
        return await self._post("/info", {
            "type": "l2Book",
            "coin": coin
        })
    
    async def get_candles(
        self,
        coin: str,
        interval: str = "1h",
        start_time: int = None,
        end_time: int = None
    ) -> List[Dict]:
        """
        获取 K 线数据
        
        Args:
            coin: 币种
            interval: 时间间隔 (1m, 5m, 15m, 30m, 1h, 4h, 1d)
            start_time: 开始时间（毫秒）
            end_time: 结束时间（毫秒）
        """
        req = {
            "coin": coin,
            "interval": interval
        }
        if start_time:
            req["startTime"] = start_time
        if end_time:
            req["endTime"] = end_time
        
        return await self._post("/info", {
            "type": "candleSnapshot",
            "req": req
        })
    
    async def get_funding_history(
        self,
        coin: str,
        start_time: int = None
    ) -> List[Dict]:
        """
        获取资金费率历史
        
        Args:
            coin: 币种
            start_time: 开始时间（毫秒）
        """
        payload = {
            "type": "fundingHistory",
            "coin": coin
        }
        if start_time:
            payload["startTime"] = start_time
        
        return await self._post("/info", payload)
    
    # ========== 地址分析相关 ==========
    
    async def analyze_address(self, address: str) -> Dict:
        """
        分析地址的交易表现
        
        Returns:
            {
                'total_pnl': float,
                'win_rate': float,
                'trade_count': int,
                'avg_leverage': float,
                'positions': list
            }
        """
        # 获取账户状态
        state = await self.get_user_state(address)
        
        # 获取交易记录
        fills = await self.get_user_fills(address)
        
        # 计算指标
        total_pnl = float(state.get('marginSummary', {}).get('totalRawPnl', 0))
        
        # 计算胜率（简化版：按单笔成交）
        if fills:
            wins = sum(1 for f in fills if float(f.get('closedPnl', 0)) > 0)
            win_rate = wins / len(fills)
        else:
            win_rate = 0
        
        # 当前持仓
        positions = []
        for pos in state.get('assetPositions', []):
            p = pos.get('position', {})
            size = float(p.get('szi', 0))
            if size != 0:
                positions.append({
                    'coin': p.get('coin'),
                    'side': 'long' if size > 0 else 'short',
                    'size': abs(size),
                    'entry_price': float(p.get('entryPx', 0)),
                    'unrealized_pnl': float(p.get('unrealizedPnl', 0)),
                    'leverage': float(p.get('leverage', {}).get('value', 1))
                })
        
        return {
            'address': address,
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'trade_count': len(fills),
            'positions': positions
        }
    
    async def get_address_positions(self, address: str) -> List[Dict]:
        """获取地址当前持仓（简化版）"""
        state = await self.get_user_state(address)
        
        positions = []
        for pos in state.get('assetPositions', []):
            p = pos.get('position', {})
            size = float(p.get('szi', 0))
            if size != 0:
                positions.append({
                    'coin': p.get('coin'),
                    'side': 'long' if size > 0 else 'short',
                    'size': abs(size)
                })
        
        return positions


# 使用示例
async def main():
    client = HyperliquidClient()
    
    # 获取市场数据
    mids = await client.get_all_mids()
    print(f"BTC: ${mids.get('BTC', 'N/A')}")
    
    # 获取 K 线
    candles = await client.get_candles("BTC", "1h")
    print(f"Candles count: {len(candles)}")
    
    # 分析某个地址（示例地址）
    # analysis = await client.analyze_address("0x...")
    # print(analysis)


if __name__ == "__main__":
    asyncio.run(main())
