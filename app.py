"""
智慧输灰高级模块 - Web 应用入口
===================================
基于 Flask + TDengine 的 Web 监测系统
风格: ICS 工业控制平台 UI
"""

import taos
from datetime import datetime, timedelta
from typing import Any

from flask import Flask, render_template, jsonify, request

# ---------------------------------------------------------------------------
# Flask 应用
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.config.update(SECRET_KEY="ash_web_2026", DEBUG=False)

# ---------------------------------------------------------------------------
# TDengine 工具
# ---------------------------------------------------------------------------
TD_HOST = "localhost"
TD_PORT = 6030
TD_USER = "root"
TD_PASS = "taosdata"
TD_DB = "ash_system"


def td_conn():
    """创建 TDengine 连接。"""
    c = taos.connect(host=TD_HOST, port=TD_PORT, user=TD_USER, password=TD_PASS)
    cur = c.cursor()
    cur.execute(f"USE {TD_DB};")
    return c, cur


def query_one(cur, sql: str) -> Any | None:
    """查询单行单列。"""
    try:
        cur.execute(sql)
        r = cur.fetchone()
        return r[0] if r else None
    except Exception:
        return None


def query_all(cur, sql: str) -> list:
    """查询多行。"""
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception:
        return []


def fetch_latest(tbl: str) -> dict | None:
    """获取指定子表的最新数据。"""
    try:
        c, cur = td_conn()
        cur.execute(
            f"SELECT ts, val, unit FROM {tbl} ORDER BY ts DESC LIMIT 1;"
        )
        r = cur.fetchone()
        cur.close(); c.close()
        if r:
            return {"ts": str(r[0])[:19], "val": float(r[1]), "unit": str(r[2])}
    except Exception:
        pass
    return None


# 测点元信息（用于前端展示）
POINT_META: list[tuple[str, str, str, str, str]] = [
    # (表名, 中文名, 分类, 图标, 单位)
    ("t_boiler_load",        "锅炉负荷",    "锅炉侧",    "fa-fire",           "%"),
    ("t_flue_gas_volume",    "烟气量",      "锅炉侧",    "fa-smog",           "kNm³/h"),
    ("t_exhaust_temp",       "排烟温度",    "锅炉侧",    "fa-temperature-high","°C"),
    ("t_ash_temperature",    "灰温",        "锅炉侧",    "fa-thermometer-half","°C"),
    ("t_dust_concentration", "粉尘排放浓度", "除尘侧",    "fa-wind",           "mg/Nm³"),
    ("t_dust_diff_pressure", "除尘器压差",   "除尘侧",    "fa-tachometer-alt", "Pa"),
    ("t_convey_pressure",    "输送气压",     "输灰系统",  "fa-gauge-high",     "MPa"),
    ("t_convey_pipe_density","管道输灰浓度", "输灰系统",  "fa-chart-simple",   "g/m³"),
    ("t_convey_speed",       "输灰速度",     "输灰系统",  "fa-forward",        "m/s"),
    ("t_hopper_ash_f1",      "#1电场灰量",  "输灰系统",  "fa-cube",           "t/h"),
    ("t_hopper_ash_f2",      "#2电场灰量",  "输灰系统",  "fa-cube",           "t/h"),
    ("t_hopper_ash_f3",      "#3电场灰量",  "输灰系统",  "fa-cube",           "t/h"),
    ("t_hopper_ash_f4",      "#4电场灰量",  "输灰系统",  "fa-cube",           "t/h"),
    ("t_flyash_level",       "飞灰液位",     "灰库/灰泵", "fa-water",          "%"),
    ("t_ashbin_level",       "灰库液位",     "灰库/灰泵", "fa-database",       "%"),
    ("t_ashpump_level",      "灰泵液位",     "灰库/灰泵", "fa-tint",           "%"),
    ("t_flyash_pressure",    "飞灰压力",     "灰库/灰泵", "fa-compress",       "kPa"),
    ("t_air_compressor_current","空压机电流", "空压机/能耗", "fa-bolt",         "A"),
    ("t_energy_consumption", "系统能耗",     "空压机/能耗", "fa-chart-area",   "kWh"),
    ("t_convey_efficiency",  "输灰效率",     "空压机/能耗", "fa-percent",      "%"),
    ("t_equipment_status",   "设备运行状态",  "设备状态",  "fa-microchip",      ""),
]

# ---------------------------------------------------------------------------
# 路由 - 页面
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", page_title="系统概览", now=datetime.now())

@app.route("/real_time")
def real_time():
    return render_template("real_time.html", page_title="实时监测", now=datetime.now())

@app.route("/optimization")
def optimization():
    return render_template("optimization.html", page_title="优化分析", now=datetime.now())

@app.route("/history")
def history():
    points = [{"tbl": t, "name": n, "category": c, "icon": i, "unit": u}
              for t, n, c, i, u in POINT_META]
    return render_template("history.html", page_title="历史数据", now=datetime.now(), points=points)

@app.route("/fault_diagnosis")
def fault_diagnosis():
    return render_template("fault_diagnosis.html", page_title="故障诊断", now=datetime.now())

# ---------------------------------------------------------------------------
# API - 仪表板概览
# ---------------------------------------------------------------------------

@app.route("/api/overview")
def api_overview():
    """系统概览关键指标。"""
    try:
        c, cur = td_conn()
        load = query_one(cur, "SELECT val FROM t_boiler_load ORDER BY ts DESC LIMIT 1;") or 50
        eff = query_one(cur, "SELECT val FROM t_convey_efficiency ORDER BY ts DESC LIMIT 1;") or 0
        dust = query_one(cur, "SELECT val FROM t_dust_concentration ORDER BY ts DESC LIMIT 1;") or 0
        energy = query_one(cur, "SELECT val FROM t_energy_consumption ORDER BY ts DESC LIMIT 1;") or 0
        echo2 = query_one(cur, "SELECT val FROM t_ashbin_level ORDER BY ts DESC LIMIT 1;") or 0

        # 过去1小时平均
        h1 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        avg_eff = query_one(cur, f"SELECT AVG(val) FROM t_convey_efficiency WHERE ts >= '{h1}';") or 0
        avg_load = query_one(cur, f"SELECT AVG(val) FROM t_boiler_load WHERE ts >= '{h1}';") or 0

        # 告警数
        alert_cnt = query_one(cur, "SELECT COUNT(*) FROM ae_unit3 WHERE alert_level >= 3;") or 0

        cur.close(); c.close()

        return jsonify({
            "boiler_load": round(load, 1),
            "efficiency": round(eff, 1),
            "avg_efficiency": round(avg_eff, 1),
            "dust_concentration": round(dust, 2),
            "energy": round(energy, 1),
            "ashbin_level": round(echo2, 1),
            "avg_load": round(avg_load, 1),
            "alert_count": int(alert_cnt),
            "status": "运行中",
            "uptime": "在线",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/points")
def api_all_points():
    """获取所有测点最新值。"""
    results = []
    for tbl, name, cat, icon, unit in POINT_META:
        d = fetch_latest(tbl)
        if d:
            results.append({
                "tbl": tbl, "name": name, "category": cat, "icon": icon,
                "val": d["val"], "unit": d["unit"], "ts": d["ts"],
            })
    return jsonify(results)


@app.route("/api/trend/<tbl>")
def api_trend(tbl: str):
    """获取指定测点的近期趋势数据。"""
    minutes = request.args.get("minutes", 30, type=int)
    since = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        c, cur = td_conn()
        rows = query_all(cur, f"SELECT ts, val FROM {tbl} WHERE ts >= '{since}' ORDER BY ts ASC;")
        cur.close(); c.close()
        times = [str(r[0])[11:19] for r in rows]
        vals = [float(r[1]) for r in rows]
        return jsonify({"times": times, "values": vals})
    except Exception as e:
        return jsonify({"error": str(e), "times": [], "values": []}), 500


# ---------------------------------------------------------------------------
# API - 实时监测
# ---------------------------------------------------------------------------

@app.route("/api/equipment_status")
def api_equipment_status():
    """设备状态 (从最新数据推算)。"""
    try:
        c, cur = td_conn()
        status = query_one(cur, "SELECT val FROM t_equipment_status ORDER BY ts DESC LIMIT 1;") or 1
        load = query_one(cur, "SELECT val FROM t_boiler_load ORDER BY ts DESC LIMIT 1;") or 50
        eff = query_one(cur, "SELECT val FROM t_convey_efficiency ORDER BY ts DESC LIMIT 1;") or 0
        convey_p = query_one(cur, "SELECT val FROM t_convey_pressure ORDER BY ts DESC LIMIT 1;") or 0
        cur.close(); c.close()

        s = int(status)
        return jsonify({
            "overall": "normal" if s == 1 else ("fault" if s == 2 else "stopped"),
            "boiler_load": round(load, 1),
            "efficiency": round(eff, 1),
            "convey_pressure": round(convey_p, 3),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/latest/<tbl>")
def api_latest(tbl: str):
    """获取单个测点最新值。"""
    d = fetch_latest(tbl)
    if d:
        return jsonify(d)
    return jsonify({"error": "no data"}), 404


# ---------------------------------------------------------------------------
# API - 优化分析
# ---------------------------------------------------------------------------

OPTIMIZATION_PLANS = [
    {
        "id": "PLAN-EC-001", "name": "低负荷节能运行方案",
        "condition": "锅炉负荷 < 50%",
        "actions": ["降低输送气压至 0.25-0.35 MPa", "减少空压机运行数量至 1 台",
                     "延长输灰周期至 15-20 分钟", "关闭非必要输灰支路"],
        "expected_saving": "15-25% 能耗降低", "risk": "低",
    },
    {
        "id": "PLAN-EC-002", "name": "中负荷经济运行方案",
        "condition": "50% ≤ 锅炉负荷 < 75%",
        "actions": ["维持输送气压 0.35-0.50 MPa", "空压机运行 1-2 台",
                     "输灰周期 10-15 分钟", "根据灰斗灰量动态调整输灰频率"],
        "expected_saving": "5-10% 能耗降低", "risk": "低",
    },
    {
        "id": "PLAN-EC-003", "name": "高负荷保产运行方案",
        "condition": "锅炉负荷 ≥ 75%",
        "actions": ["提高输送气压至 0.50-0.65 MPa", "空压机运行 2 台",
                     "缩短输灰周期至 5-10 分钟", "全部输灰支路投入运行"],
        "expected_saving": "保障输灰能力为首要目标", "risk": "中",
    },
]

EXPERT_RULES = [
    {"name": "空压机过载", "condition": "空压机电流 > 80A",
     "conclusion": "空压机电流过高，可能机械卡涩或电气故障",
     "suggestion": "检查空压机运行声音、电流波动，排查电气回路"},
    {"name": "输灰管道堵塞预警", "condition": "输送气压 > 0.75MPa 且 浓度 > 250g/m³",
     "conclusion": "输送气压偏高且浓度大，输灰管道可能堵塞",
     "suggestion": "检查输灰管道压力波动，启动反吹扫程序"},
    {"name": "粉尘排放超标", "condition": "粉尘排放浓度 > 25mg/Nm³",
     "conclusion": "粉尘排放浓度偏高，可能存在滤袋破损或除尘效率下降",
     "suggestion": "检查除尘器出口排放，排查滤袋破损情况"},
    {"name": "输灰效率偏低", "condition": "输灰效率 < 70%",
     "conclusion": "输灰效率低于正常水平，系统运行不经济",
     "suggestion": "优化输灰周期参数，检查输灰管道阻力"},
]


@app.route("/api/optimization")
def api_optimization():
    """优化分析数据。"""
    try:
        c, cur = td_conn()
        load = query_one(cur, "SELECT val FROM t_boiler_load ORDER BY ts DESC LIMIT 1;") or 50
        eff = query_one(cur, "SELECT val FROM t_convey_efficiency ORDER BY ts DESC LIMIT 1;") or 0
        energy = query_one(cur, "SELECT val FROM t_energy_consumption ORDER BY ts DESC LIMIT 1;") or 0

        h1 = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        avg_load = query_one(cur, f"SELECT AVG(val) FROM t_boiler_load WHERE ts >= '{h1}';") or 50
        avg_eff = query_one(cur, f"SELECT AVG(val) FROM t_convey_efficiency WHERE ts >= '{h1}';") or 0
        avg_energy = query_one(cur, f"SELECT AVG(val) FROM t_energy_consumption WHERE ts >= '{h1}';") or 0
        cur.close(); c.close()
    except Exception:
        load = eff = avg_load = avg_eff = avg_energy = 50

    # 匹配方案
    active = [p for p in OPTIMIZATION_PLANS
              if ("< 50" in p["condition"] and load < 50)
              or ("< 75" in p["condition"] and "50" in p["condition"] and 50 <= load < 75)
              or ("≥ 75" in p["condition"] and load >= 75)]

    # 效率评价
    if avg_eff >= 85: rating = "优秀"
    elif avg_eff >= 75: rating = "良好"
    elif avg_eff >= 65: rating = "一般"
    else: rating = "较差"

    energy_saving = round((1 - eff / max(avg_eff, 1)) * 100, 1) if avg_eff > 0 else 0

    return jsonify({
        "load": round(load, 1),
        "efficiency": round(eff, 1),
        "avg_load": round(avg_load, 1),
        "avg_efficiency": round(avg_eff, 1),
        "avg_energy": round(avg_energy, 1),
        "energy_saving": max(0, energy_saving),
        "rating": rating,
        "active_plans": active,
    })


@app.route("/api/expert_diagnosis")
def api_expert_diagnosis():
    """专家诊断 - 从数据库读最新值匹配规则。"""
    try:
        c, cur = td_conn()
        latest = {}
        for tbl in [
            "t_boiler_load", "t_convey_pressure",
            "t_convey_pipe_density", "t_air_compressor_current",
            "t_dust_concentration", "t_convey_efficiency",
            "t_ashbin_level", "t_exhaust_temp",
            "t_equipment_status",
        ]:
            r = query_one(cur, f"SELECT val FROM {tbl} ORDER BY ts DESC LIMIT 1;")
            if r is not None:
                latest[tbl] = float(r)
        load = latest.get("t_boiler_load", 50)
        cur.close(); c.close()
    except Exception:
        latest = {}
        load = 50

    triggered = []
    if latest.get("t_air_compressor_current", 0) > 80:
        triggered.append(EXPERT_RULES[0])
    if latest.get("t_convey_pressure", 0) > 0.75 and latest.get("t_convey_pipe_density", 0) > 250:
        triggered.append(EXPERT_RULES[1])
    if latest.get("t_dust_concentration", 0) > 25:
        triggered.append(EXPERT_RULES[2])
    if latest.get("t_convey_efficiency", 100) < 70:
        triggered.append(EXPERT_RULES[3])

    return jsonify({
        "load": round(load, 1),
        "rules_triggered": triggered,
    })


@app.route("/api/history/<tbl>")
def api_history(tbl: str):
    """历史数据查询。"""
    hours = request.args.get("hours", 24, type=int)
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        c, cur = td_conn()
        rows = query_all(cur, f"SELECT ts, val FROM {tbl} WHERE ts >= '{since}' ORDER BY ts ASC;")
        cur.close(); c.close()
        return jsonify({
            "times": [str(r[0])[:19] for r in rows],
            "values": [float(r[1]) for r in rows],
        })
    except Exception as e:
        return jsonify({"error": str(e), "times": [], "values": []}), 500


@app.route("/api/alerts")
def api_alerts():
    """告警事件查询。"""
    limit = request.args.get("limit", 30, type=int)
    level = request.args.get("level", 0, type=int)
    try:
        c, cur = td_conn()
        where = f"WHERE alert_level >= {level}" if level > 0 else ""
        rows = query_all(cur,
            f"SELECT ts, alert_level, alert_level_name, source_tag, "
            f"  source_value, alert_message, suggested_action "
            f"FROM ae_unit3 {where} ORDER BY ts DESC LIMIT {limit};")
        cur.close(); c.close()
        return jsonify([{
            "ts": str(r[0])[:19], "level": int(r[1]), "level_name": str(r[2]),
            "source_tag": str(r[3]), "source_value": float(r[4]) if r[4] else 0,
            "message": str(r[5]), "action": str(r[6]) if r[6] else "",
        } for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  智慧输灰高级模块 - Web 应用")
    print("=" * 60)
    print(f"  TDengine: {TD_HOST}:{TD_PORT}/{TD_DB}")
    print(f"  访问地址: http://localhost:5000")
    print(f"  Ctrl+C 停止服务")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
