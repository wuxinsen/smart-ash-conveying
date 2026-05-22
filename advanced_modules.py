"""
智慧输灰高级模块 - 监测分析与优化系统 (CLI 版)
======================================
通过 database 模块读写 TDengine，无直接 taos 依赖。
功能:
  1. 实时监测面板 - 全量测点数据展示
  2. 趋势分析 - 关键指标变化趋势
  3. 告警管理 - 告警事件查询
  4. 能效分析 - 系统能耗与效率分析
  5. 专家诊断 - 基于知识库的故障推理
  6. 负荷联动优化 - 优化方案推荐
  7. 历史数据查询 - 指定时间段数据检索
"""

import sys
from datetime import datetime, timedelta

import database as db
from config import (
    POINTS, POINT_UNITS, ALERT_THRESHOLDS,
    EXPERT_RULES, OPTIMIZATION_PLANS,
)
from settings import TD_DB


# =============================================================================
# 辅助: 测点名查找
# =============================================================================

def _point_name(tbl: str) -> str:
    for t, n, _, _, _ in POINTS:
        if t == tbl:
            return n
    return tbl


# =============================================================================
# 1. 实时监测面板
# =============================================================================

def show_dashboard() -> None:
    """显示全量测点实时监测面板。"""
    latest = db.fetch_all_latest()

    print("\n" + "=" * 80)
    print("  #3机组 智慧输灰高级模块 - 实时监测面板")
    print("=" * 80)

    categories = {
        "锅炉侧":         ["t_boiler_load", "t_flue_gas_volume", "t_exhaust_temp", "t_ash_temperature"],
        "除尘侧":         ["t_dust_concentration", "t_dust_diff_pressure"],
        "输灰系统":       ["t_convey_pressure", "t_convey_pipe_density", "t_convey_speed",
                          "t_hopper_ash_f1", "t_hopper_ash_f2", "t_hopper_ash_f3", "t_hopper_ash_f4"],
        "灰库/灰泵":      ["t_flyash_level", "t_ashbin_level", "t_ashpump_level", "t_flyash_pressure"],
        "空压机/能耗":    ["t_air_compressor_current", "t_energy_consumption", "t_convey_efficiency"],
        "设备状态":       ["t_equipment_status", "t_value_status"],
        "标准信号":       ["t_counter", "t_random", "t_sinusoid", "t_triangle", "t_sawtooth", "t_square",
                          "t_compressor_pressure", "t_ashpump_leverl"],
    }

    for cat_name, tags in categories.items():
        print(f"\n  [{cat_name}]")
        for tag in tags:
            val = latest.get(tag)
            if val is not None:
                d = db.fetch_latest(tag)
                ts_str = d["ts"] if d else "--"
                unit = POINT_UNITS.get(tag, "")
                name = _point_name(tag)
                print(f"    {name:<12} ({tag}) "
                      f"{val:>10.4f} {unit:<8}  @ {ts_str}")

    print("\n" + "=" * 80)


# =============================================================================
# 2. 趋势分析
# =============================================================================

def show_trend(tbl: str, minutes: int = 30) -> None:
    """显示指定测点的近期变化趋势。"""
    point_name = _point_name(tbl)
    unit = POINT_UNITS.get(tbl, "")

    since = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.query_all(
        f"SELECT ts, val FROM {tbl} WHERE ts >= '{since}' ORDER BY ts ASC;"
    )
    if not rows:
        print(f"[提示] {point_name} ({tbl}) 在最近 {minutes} 分钟内无数据。")
        return

    values = [float(r[1]) for r in rows]
    v_min, v_max, v_avg = min(values), max(values), sum(values) / len(values)
    v_last = values[-1]
    v_first = values[0]
    change = v_last - v_first

    print(f"\n  [{point_name} ({tbl})] 趋势分析 (过去{minutes}分钟)")
    print(f"  {'=' * 60}")
    print(f"    当前值: {v_last:.4f} {unit}")
    print(f"    平均值: {v_avg:.4f} {unit}")
    print(f"    最小值: {v_min:.4f} {unit}")
    print(f"    最大值: {v_max:.4f} {unit}")
    print(f"    变化量: {change:+.4f} {unit}")
    print(f"    数据点: {len(rows)} 条")

    # ASCII 趋势图
    if v_max > v_min:
        h = 10
        for i in range(h):
            threshold = v_max - (v_max - v_min) * i / (h - 1)
            lower = v_max - (v_max - v_min) * (i + 1) / (h - 1)
            line_chars = ""
            for v in values:
                if lower <= v <= threshold:
                    line_chars += "█"
                else:
                    line_chars += " "
            bar_len = min(60, len(line_chars))
            print(f"    {threshold:>7.2f} |{line_chars[:bar_len]}")
        print(f"    {'':>7} +{'-' * bar_len}")
        print(f"    {'':>7}  {since[:16]}")

    # 关键判断
    if change > 0:
        print(f"  ═> 趋势: 上升 (+{change:.2f} {unit})")
    elif change < 0:
        print(f"  ═> 趋势: 下降 ({change:.2f} {unit})")
    else:
        print("  ═> 趋势: 平稳")

    # 检查阈值
    for tag, lo_lo, lo, hi, hi_hi, desc in ALERT_THRESHOLDS:
        if tag == tbl:
            if hi_hi and v_last > hi_hi:
                print(f"  ⚠ 告警: {desc} - 高高限 ({hi_hi})")
            elif hi and v_last > hi:
                print(f"  ⚠ 注意: {desc} - 高限 ({hi})")
            if lo_lo and v_last < lo_lo:
                print(f"  ⚠ 告警: {desc} - 低低限 ({lo_lo})")
            elif lo and v_last < lo:
                print(f"  ⚠ 注意: {desc} - 低限 ({lo})")


# =============================================================================
# 3. 告警管理
# =============================================================================

def show_alerts(limit: int = 20, level_filter: int | None = None) -> None:
    """查询告警事件。"""
    alerts = db.fetch_alerts(limit, level_filter or 0)
    if not alerts:
        print("[信息] 当前无告警记录。")
        return

    print(f"\n  [告警事件] 最新 {limit} 条")
    print(f"  {'=' * 80}")
    for a in alerts:
        print(f"  {a['ts']} [{a['level_name']:<12}] {a['source_tag']:<20} {a['message']}")
        if a.get("action"):
            print(f"    └─ 建议: {a['action']}")


# =============================================================================
# 4. 能效分析
# =============================================================================

def show_efficiency(minutes: int = 60) -> None:
    """显示系统能效分析。"""
    since = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    db_name = TD_DB

    avg_energy = db.query_one(
        f"SELECT AVG(val) FROM {db_name}.t_energy_consumption WHERE ts >= '{since}';"
    ) or 0

    eff_row = db.query_one(
        f"SELECT AVG(val), MAX(val), MIN(val) FROM {db_name}.t_convey_efficiency "
        f"WHERE ts >= '{since}';"
    ) or (0, 0, 0)
    avg_eff, max_eff, min_eff = float(eff_row[0] or 0), float(eff_row[1] or 0), float(eff_row[2] or 0)

    load_row = db.query_one(
        f"SELECT AVG(val), MAX(val), MIN(val) FROM {db_name}.t_boiler_load "
        f"WHERE ts >= '{since}';"
    ) or (0, 0, 0)
    avg_load, max_load, min_load = float(load_row[0] or 0), float(load_row[1] or 0), float(load_row[2] or 0)

    avg_f1 = db.query_one(
        f"SELECT AVG(val) FROM {db_name}.t_hopper_ash_f1 WHERE ts >= '{since}';"
    ) or 0
    unit_energy = avg_energy / max(float(avg_f1), 0.1)

    print(f"\n  [#3机组能效分析报告] 过去{minutes}分钟")
    print(f"  {'=' * 60}")
    print(f"    锅炉平均负荷:     {avg_load:.1f}%")
    print(f"    负荷范围:         {min_load:.1f}% ~ {max_load:.1f}%")
    print(f"    平均能耗:         {avg_energy:.1f} kWh")
    print(f"    平均输灰效率:     {avg_eff:.1f}%")
    print(f"    效率范围:         {min_eff:.1f}% ~ {max_eff:.1f}%")
    print(f"    单位能耗:         {unit_energy:.2f} kWh/t")

    print(f"\n    能效评价: ", end="")
    if avg_eff >= 85:
        print("优秀")
    elif avg_eff >= 75:
        print("良好")
    elif avg_eff >= 65:
        print("一般 - 建议优化")
    else:
        print("较差 - 需排查原因")

    if avg_load < 50:
        print("    建议: 当前低负荷运行, 推荐启用节能运行方案")
        print("          可降低能耗 15-25%")


# =============================================================================
# 5. 专家诊断系统
# =============================================================================

def run_expert_diagnosis() -> None:
    """
    基于知识库的正向推理故障诊断。
    读取各测点最新值，匹配知识库规则，输出诊断结果。
    """
    values = db.fetch_all_latest()
    if not values:
        print("[提示] 无数据可用于诊断。")
        return

    load = values.get("t_boiler_load", 50)

    print(f"\n  [#3机组 智慧输灰 - 专家诊断系统]")
    print(f"  {'=' * 70}")
    print(f"  当前工况: 锅炉负荷 {load:.1f}%")
    print(f"  诊断规则数: {len(EXPERT_RULES)}")
    print(f"  {'=' * 70}")

    triggered = 0
    for rule_name, conditions, conclusion, suggestion, fault_type in EXPERT_RULES:
        match = True
        cond_details = []
        for tag, comp, threshold in conditions:
            if tag not in values:
                match = False
                break
            v = values[tag]
            if comp == "gt" and not (v > threshold):
                match = False; break
            if comp == "lt" and not (v < threshold):
                match = False; break
            if comp == "gte" and not (v >= threshold):
                match = False; break
            if comp == "lte" and not (v <= threshold):
                match = False; break
            if comp == "eq" and not (abs(v - threshold) < 0.01):
                match = False; break
            cond_details.append(f"{tag}={v:.2f}")
        if not match:
            continue

        triggered += 1
        print(f"\n  ┌─ [规则触发] {rule_name}")
        print(f"  ├─ 条件: {', '.join(cond_details)}")
        print(f"  ├─ 诊断: {conclusion}")
        print(f"  ├─ 类型: {fault_type}")
        print(f"  └─ 建议: {suggestion}")

    if triggered == 0:
        print("\n  诊断结果: 各参数正常，未触发故障规则。")

    print(f"\n  {'=' * 70}")


# =============================================================================
# 6. 负荷联动优化方案推荐
# =============================================================================

def show_optimization_plans() -> None:
    """根据当前负荷推荐优化方案。"""
    values = db.fetch_all_latest()
    if not values:
        print("[提示] 无负荷数据。")
        return

    load = values.get("t_boiler_load", 50)
    efficiency = values.get("t_convey_efficiency", 0)

    print(f"\n  [#3机组 智慧输灰 - 优化方案推荐]")
    print(f"  {'=' * 70}")
    print(f"  当前负荷: {load:.1f}% | 当前输灰效率: {efficiency:.1f}%")
    print(f"  {'=' * 70}")

    active_plans = []
    for plan in OPTIMIZATION_PLANS:
        condition = plan["condition"]
        matched = False
        if "t_boiler_load < 50" in condition and load < 50:
            matched = True
        elif "t_boiler_load < 75" in condition and "50" in condition and 50 <= load < 75:
            matched = True
        elif "t_boiler_load ≥ 75" in condition and load >= 75:
            matched = True
        if matched:
            active_plans.append(plan)

    if active_plans:
        for plan in active_plans:
            print(f"\n  >> [{plan['id']}] {plan['name']}")
            print(f"     适用条件: {plan['condition']}")
            for i, action in enumerate(plan["actions"], 1):
                print(f"      {i}. {action}")
            print(f"     预期效果: {plan['expected_saving']}")
            print(f"     风险等级: {plan['risk']}")
    else:
        print("\n  当前工况无匹配的优化方案。")

    print(f"\n  {'=' * 70}")


# =============================================================================
# 7. 历史数据查询
# =============================================================================

def query_history(tbl: str, start: str, end: str) -> None:
    """查询指定时间段的历史数据。"""
    point_name = _point_name(tbl)
    unit = POINT_UNITS.get(tbl, "")

    rows = db.query_all(
        f"SELECT ts, val, quality FROM {tbl} "
        f"WHERE ts >= '{start}' AND ts <= '{end}' "
        f"ORDER BY ts ASC LIMIT 100;"
    )

    if not rows:
        print(f"[提示] {point_name} 在指定时间段内无数据。")
        return

    count = len(rows)
    values = [float(r[1]) for r in rows]
    print(f"\n  [{point_name}] 历史数据查询")
    print(f"  {'=' * 60}")
    print(f"  时间段: {start} ~ {end}")
    print(f"  数据量: {count} 条")
    print(f"  范围:   {min(values):.4f} ~ {max(values):.4f} {unit}")
    print(f"  平均值: {sum(values)/count:.4f} {unit}")
    print(f"\n  数据列表(前20条):")
    print(f"  {'时间':<22} {'值':>12} {'质量':>6}")
    print(f"  {'-' * 42}")
    for r in rows[:20]:
        print(f"  {str(r[0])[:19]:<22} {float(r[1]):>12.4f} {int(r[2]):>6}")


# =============================================================================
# 主菜单
# =============================================================================

def main_menu():
    """交互式主菜单。"""
    while True:
        print("\n" + "=" * 60)
        print("  智慧输灰高级模块 v2.0 - 主菜单")
        print("=" * 60)
        print("  1. 实时监测面板")
        print("  2. 趋势分析")
        print("  3. 告警管理")
        print("  4. 能效分析")
        print("  5. 专家诊断系统")
        print("  6. 负荷联动优化")
        print("  7. 历史数据查询")
        print("  8. 运行所有模块")
        print("  0. 退出")
        print("=" * 60)

        choice = input("  请选择 [0-8]: ").strip()

        if choice == "1":
            show_dashboard()
        elif choice == "2":
            print("\n  可选测点:")
            for tbl, name, _, _, _ in POINTS:
                print(f"    {tbl:<25} {name}")
            tag = input("  输入测点表名: ").strip()
            if tag:
                show_trend(tag)
        elif choice == "3":
            show_alerts()
        elif choice == "4":
            show_efficiency()
        elif choice == "5":
            run_expert_diagnosis()
        elif choice == "6":
            show_optimization_plans()
        elif choice == "7":
            print("\n  可选测点:")
            for tbl, name, _, _, _ in POINTS:
                print(f"    {tbl:<25} {name}")
            tag = input("  输入测点表名: ").strip()
            start = input("  开始时间 (YYYY-MM-DD HH:MM:SS): ").strip()
            end = input("  结束时间 (YYYY-MM-DD HH:MM:SS): ").strip()
            if tag and start and end:
                query_history(tag, start, end)
        elif choice == "8":
            print("\n  运行所有模块...")
            show_dashboard()
            show_efficiency()
            show_alerts(limit=5)
            run_expert_diagnosis()
            show_optimization_plans()
        elif choice == "0":
            print("\n  退出程序。")
            break
        else:
            print("\n  无效选择，请重试。")

        if choice not in ("0", "8"):
            input("\n  按 Enter 继续...")


# =============================================================================
# 命令行快速入口
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "dashboard":
            show_dashboard()
        elif cmd == "trend" and len(sys.argv) > 2:
            show_trend(sys.argv[2])
        elif cmd == "alerts":
            show_alerts()
        elif cmd == "efficiency":
            show_efficiency()
        elif cmd == "diagnosis":
            run_expert_diagnosis()
        elif cmd == "optimize":
            show_optimization_plans()
        elif cmd == "history" and len(sys.argv) > 4:
            query_history(sys.argv[2], sys.argv[3], sys.argv[4])
        else:
            print("用法: python advanced_modules.py [command]")
            print("命令: dashboard, trend <tag>, alerts, efficiency, diagnosis, optimize, history <tag> <start> <end>")
    else:
        main_menu()
