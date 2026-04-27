"""
CryptoAnalysis 策略 API 服务

启动方式：
  cd /home/ubuntu/CryptoAnalysis
  venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 18888

后台启动：
  nohup venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 18888 > logs/api.log 2>&1 &

接口文档：
  http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes.strategies import router as strategies_router

# ── 日志 ────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/api.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── FastAPI 应用 ─────────────────────────────────────────────
app = FastAPI(
    title="CryptoAnalysis Strategy API",
    description="Hyperliquid 反脆弱策略监控服务 API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategies_router)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    """健康检查"""
    return {"status": "ok", "version": "0.2.0"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Strategy API 服务启动")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("Strategy API 服务关闭")
