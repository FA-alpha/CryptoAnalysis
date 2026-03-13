"""
Coinglass API 数据采集模块
"""

import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd


class CoinglassClient:
    """Coinglass API 客户端"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://open-api-v4.coinglass.com/api"
        # V4 API 使用 CG-API-KEY 请求头
        self.headers = {
            "accept": "application/json",
            "CG-API-KEY": api_key
        }
    
    async def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """发送 API 请求"""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as resp:
                if resp.status != 200:
                    raise Exception(f"API Error: {resp.status}")
                data = await resp.json()
                
                if data.get('code') != '0':
                    raise Exception(f"API Error: {data.get('msg')}")
                
                return data.get('data', {})
    
    async def get_long_short_ratio(
        self, 
        symbol: str = "BTC",
        exchange: str = "Binance",
        interval: str = "h4",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        获取多空账户比历史数据
        
        Args:
            symbol: 币种 (BTC, ETH, SOL, ...)
            exchange: 交易所 (Binance, OKX, Bybit, ...)
            interval: 时间间隔 (m5, m15, h1, h4, h12, h24)
            limit: 返回数量
        
        Returns:
            DataFrame with columns: timestamp, longAccount, shortAccount, longShortRatio
        """
        data = await self._request(
            "/futures/global-long-short-account-ratio/history",
            params={
                "symbol": symbol,
                "exchange": exchange,
                "interval": interval,
                "limit": limit
            }
        )
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['createTime'], unit='ms')
        df['longShortRatio'] = df['longAccount'] / df['shortAccount']
        
        return df[['timestamp', 'longAccount', 'shortAccount', 'longShortRatio']]
    
    async def get_top_trader_ratio(
        self,
        symbol: str = "BTC",
        exchange: str = "Binance",
        interval: str = "h4",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        获取顶级交易者多空比
        """
        data = await self._request(
            "/futures/top-long-short-account-ratio/history",
            params={
                "symbol": symbol,
                "exchange": exchange,
                "interval": interval,
                "limit": limit
            }
        )
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)
    
    async def get_liquidation_history(
        self,
        symbol: str = "BTC",
        interval: str = "h1",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        获取历史清算数据
        """
        data = await self._request(
            "/futures/liquidation/history",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
        )
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['createTime'], unit='ms')
        
        return df
    
    async def get_liquidation_aggregated(
        self,
        symbol: str = "BTC",
        interval: str = "5m"
    ) -> Dict:
        """
        获取聚合清算数据
        """
        return await self._request(
            "/futures/liquidation/aggregated",
            params={
                "symbol": symbol,
                "interval": interval
            }
        )
    
    async def get_funding_rate(
        self,
        symbol: str = "BTC",
        exchange: str = "Binance"
    ) -> pd.DataFrame:
        """
        获取资金费率
        """
        data = await self._request(
            "/futures/funding-rate/history",
            params={
                "symbol": symbol,
                "exchange": exchange
            }
        )
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)


# 使用示例
async def main():
    client = CoinglassClient("your_api_key")
    
    # 获取多空比
    df = await client.get_long_short_ratio("BTC", interval="h4", limit=50)
    print(df.head())
    
    # 获取清算数据
    liq = await client.get_liquidation_history("BTC", interval="h1")
    print(liq.head())


if __name__ == "__main__":
    asyncio.run(main())
