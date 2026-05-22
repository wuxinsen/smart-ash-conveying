"""
智慧输灰高级模块 - 数据库操作层
==================================
所有 TDengine 读写操作集中在这里。
其他文件通过此模块访问数据库，不再直接 import taos。
"""

import taos
from datetime import datetime, timedelta
from typing import Any

from config import POINTS, POINT_UNITS, ALERT_THRESHOLDS
from settings import TD_HOST, TD_PORT, TD_USER, TD_PASS, TD_DB

TaosCursor = Any


# =============================================================================
# 连接管理
# =============================================================================

def get_cursor() -> tuple[Any, TaosCursor]:
    """获取 TDengine 连接和游标。"""
    conn = taos.connect(host=TD_HOST, port=TD_PORT, user=TD_USER, password=TD_PASS)
    cursor = conn.cursor()
    cursor.execute(f"USE {TD_DB};")
    return conn, cursor


# =============================================================================
# 初始化 (建库建表)
# =============================================================================

def init_database() -> None:
    """初始化数据库和所有表 (幂等, 可重复执行)。"""
    conn = taos.connect(host=TD_HOST, port=TD_PORT, user=TD_USER, password=TD_PASS)
    cursor = conn.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {TD_DB} KEEP 30 DURATION 1 BUFFER 256;")
        cursor.execute(f"USE {TD_DB};")
        cursor.execute(
            "CREATE STABLE IF NOT EXISTS tag_data ("
            "  ts TIMESTAMP, val DOUBLE, unit BINARY(32), quality INT"
            ") TAGS (tag_name BINARY(64), node_id BINARY(128));"
        )
        cursor.execute(
            "CREATE STABLE IF NOT EXISTS alert_events ("
            "  ts TIMESTAMP, alert_level INT, alert_level_name BINARY(16),"
            "  source_tag BINARY(64), source_value DOUBLE,"
            "  alert_message BINARY(256), suggested_action BINARY(256)"
            ") TAGS (unit_name BINARY(64));"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ae_unit3 "
            f"USING {TD_DB}.alert_events TAGS('#3机组输灰系统');"
        )
        for tbl, tag_name, node_id, _, _ in POINTS:
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {TD_DB}.{tbl} "
                f"USING {TD_DB}.tag_data TAGS('{tag_name}', '{node_id}');"
            )
        n = len(POINTS)
        print(f"[DB] 数据库 {TD_DB} 就绪，{n} 个测点子表 + 告警表。")
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# 写入
# =============================================================================

def insert_point(tbl: str, ts: datetime, value: float, quality: int) -> None:
    """插入一条测点数据。"""
    conn, cursor = get_cursor()
    try:
        unit = POINT_UNITS.get(tbl, "")
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cursor.execute(
            f"INSERT INTO {TD_DB}.{tbl} (ts, val, unit, quality) "
            f"VALUES ('{ts_str}', {value}, '{unit}', {quality});"
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_batch(results: dict[str, float], ts: datetime, quality: int) -> None:
    """批量插入所有测点 (单条多表 INSERT，性能高)。"""
    conn, cursor = get_cursor()
    try:
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        parts = []
        for tbl, _, _, _, _ in POINTS:
            v = results.get(tbl, 0.0)
            unit = POINT_UNITS.get(tbl, "")
            parts.append(
                f"{TD_DB}.{tbl} (ts, val, unit, quality) "
                f"VALUES ('{ts_str}', {v}, '{unit}', {quality})"
            )
        cursor.execute(f"INSERT INTO {' '.join(parts)}")
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_alert(ts: datetime, level: int, level_name: str,
                 source_tag: str, source_value: float,
                 message: str, action: str = "") -> None:
    """插入一条告警记录。"""
    conn, cursor = get_cursor()
    try:
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cursor.execute(
            f"INSERT INTO {TD_DB}.ae_unit3 "
            f"(ts, alert_level, alert_level_name, source_tag, source_value, "
            f" alert_message, suggested_action) "
            f"VALUES ('{ts_str}', {level}, '{level_name}', '{source_tag}', "
            f" {source_value}, '{message}', '{action}');"
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def check_and_insert_alerts(ts: datetime, values: dict[str, float]) -> None:
    """检查所有阈值，超限则写入告警。"""
    for tag, lo_lo, lo, hi, hi_hi, desc in ALERT_THRESHOLDS:
        if tag not in values:
            continue
        v = values[tag]
        if tag == "t_equipment_status" and v == 0:
            insert_alert(ts, 3, "CRITICAL", tag, v,
                         "设备停运", "检查启停记录，排查故障原因")
        elif lo_lo is not None and v < lo_lo:
            insert_alert(ts, 4, "FATAL", tag, v,
                         f"{desc}: {v:.2f} 低于低低限 {lo_lo}", "紧急处理!")
        elif hi_hi is not None and v > hi_hi:
            insert_alert(ts, 4, "FATAL", tag, v,
                         f"{desc}: {v:.2f} 高于高高限 {hi_hi}", "紧急处理!")
        elif lo is not None and v < lo:
            insert_alert(ts, 2, "WARNING", tag, v,
                         f"{desc}: {v:.2f} 低于下限 {lo}", "关注并分析原因")
        elif hi is not None and v > hi:
            insert_alert(ts, 2, "WARNING", tag, v,
                         f"{desc}: {v:.2f} 高于上限 {hi}", "关注并分析原因")


# =============================================================================
# 读取
# =============================================================================

def query_one(sql: str) -> Any | None:
    """查询单行单列，返回第一个字段或 None。"""
    conn, cursor = get_cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchone()
        return rows[0] if rows else None
    except Exception:
        return None
    finally:
        cursor.close()
        conn.close()


def query_all(sql: str) -> list[tuple]:
    """查询多行。"""
    conn, cursor = get_cursor()
    try:
        cursor.execute(sql)
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()


def fetch_latest(tbl: str) -> dict | None:
    """获取指定子表的最新数据。"""
    rows = query_all(
        f"SELECT ts, val, unit FROM {TD_DB}.{tbl} ORDER BY ts DESC LIMIT 1;"
    )
    if rows:
        r = rows[0]
        return {"ts": str(r[0])[:19], "val": float(r[1]), "unit": str(r[2])}
    return None


def fetch_all_latest() -> dict[str, float]:
    """获取所有测点最新值，返回 {表名: 值} 字典。"""
    values = {}
    for tbl, _, _, _, _ in POINTS:
        row = query_one(f"SELECT val FROM {TD_DB}.{tbl} ORDER BY ts DESC LIMIT 1;")
        if row is not None:
            values[tbl] = float(row)
    return values


def fetch_trend(tbl: str, minutes: int = 30) -> tuple[list[str], list[float]]:
    """获取测点近期趋势数据。"""
    since = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    rows = query_all(
        f"SELECT ts, val FROM {TD_DB}.{tbl} WHERE ts >= '{since}' ORDER BY ts ASC;"
    )
    times = [str(r[0])[11:19] for r in rows]
    vals = [float(r[1]) for r in rows]
    return times, vals


def fetch_alerts(limit: int = 30, level: int = 0) -> list[dict]:
    """查询告警事件。"""
    where = f"WHERE alert_level >= {level}" if level > 0 else ""
    rows = query_all(
        f"SELECT ts, alert_level, alert_level_name, source_tag, "
        f"  source_value, alert_message, suggested_action "
        f"FROM {TD_DB}.ae_unit3 {where} ORDER BY ts DESC LIMIT {limit};"
    )
    return [{
        "ts": str(r[0])[:19], "level": int(r[1]), "level_name": str(r[2]),
        "source_tag": str(r[3]), "source_value": float(r[4]) if r[4] else 0,
        "message": str(r[5]), "action": str(r[6]) if r[6] else "",
    } for r in rows]
