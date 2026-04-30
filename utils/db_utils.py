"""
数据库工具类
自动设置时区为 Asia/Shanghai (UTC+8)
"""
import os
import pymysql
from typing import Optional
from contextlib import contextmanager
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('config/.env')

# 数据库配置（Onchain）
ONCHAIN_DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'fa-bi.cp2608aa2gcx.us-west-1.rds.amazonaws.com'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASSWORD', 'XFGAd9wJYMJqSD7C'),
    'database': os.getenv('DB_NAME', 'fourieralpha_hl'),
    'charset': 'utf8mb4'
}
    
# 数据库配置（Prod）
PROD_DB_CONFIG = {
    'host': os.getenv('PROD_DB_HOST', 'fa-02.cp2608aa2gcx.us-west-1.rds.amazonaws.com'),
    'port': int(os.getenv('PROD_DB_PORT', 3306)),
    'user': os.getenv('PROD_DB_USER', 'hl_user'),
    'password': os.getenv('PROD_DB_PASSWORD', 'B6viSUZBBgmMjHP'),
    'database': os.getenv('PROD_DB_NAME', 'fourieralpha_hl'),
    'charset': 'utf8mb4'
}
def get_connection(autocommit: bool = False) -> pymysql.Connection:
    """
    获取数据库连接（自动设置时区为北京时间）
    
    Args:
        autocommit: 是否自动提交
        
    Returns:
        数据库连接对象
    """
    conn = pymysql.connect(**PROD_DB_CONFIG, autocommit=autocommit)
    
    # 设置会话时区为北京时间
    with conn.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")
    
    return conn


def get_onchain_connection(autocommit: bool = False) -> pymysql.Connection:
    """
    获取业务数据库连接（PROD，自动设置时区为北京时间）

    Args:
        autocommit: 是否自动提交

    Returns:
        数据库连接对象
    """
    conn = pymysql.connect(**ONCHAIN_DB_CONFIG, autocommit=autocommit)

    # 设置会话时区为北京时间
    with conn.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")

    return conn


@contextmanager
def get_db():
    """
    数据库连接上下文管理器
    
    用法:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_onchain_db():
    """
    业务数据库连接上下文管理器（PROD）

    用法:
        with get_prod_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    conn = get_onchain_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(autocommit: bool = False):
    """
    数据库游标上下文管理器
    
    用法:
        with get_cursor() as cursor:
            cursor.execute(...)
    """
    conn = get_connection(autocommit=autocommit)
    cursor = conn.cursor()
    try:
        yield cursor
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def test_connection():
    """测试数据库连接和时区设置"""
    try:
        with get_cursor() as cursor:
            # 测试查询
            cursor.execute('SELECT NOW(), @@session.time_zone')
            row = cursor.fetchone()
            print(f"✅ 数据库连接成功!")
            print(f"   当前时间: {row[0]}")
            print(f"   会话时区: {row[1]}")
            return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


if __name__ == '__main__':
    test_connection()
