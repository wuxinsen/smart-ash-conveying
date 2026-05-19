"""
智慧输灰高级模块 - 配置定义
=============================
包含所有测点定义、告警阈值、专家知识库规则等
"""

from typing import Any

# =============================================================================
# 测点定义
# =============================================================================
# (子表名, 中文名称, OPC UA NodeId, 模拟类型, 参数字典)
# 模拟类型:
#   counter    - 计数器 (递增)
#   random     - 随机值 (均匀分布)
#   sinusoid   - 正弦波
#   sawtooth   - 锯齿波
#   triangle   - 三角波
#   square     - 方波
#   constant   - 常量
#   load_core  - 锅炉负荷 (日负荷曲线模拟)
#   load_follow - 跟随负荷 (与负荷联动)
#   equipment  - 设备状态 (运行/停止/故障)
#   hopper     - 灰斗灰量 (受负荷和输送影响)

POINTS: list[tuple[str, str, str, str, dict[str, Any]]] = [

    # ========== 标准信号 (UASIM 默认 + Word 文档) ==========
    ("t_counter",    "计数器",   "ns=3;i=1001", "counter",   {"min": 0, "max": 30, "step": 1}),
    ("t_random",     "随机数",   "ns=3;i=1002", "random",    {"min": -2, "max": 2}),
    ("t_sawtooth",   "锯齿波",   "ns=3;i=1003", "sawtooth",  {"min": -2, "max": 2, "period": 10}),
    ("t_sinusoid",   "正弦波",   "ns=3;i=1004", "sinusoid",  {"min": -2, "max": 2, "period": 30}),
    ("t_square",     "方波",     "ns=3;i=1005", "square",    {"min": -2, "max": 2, "period": 20}),
    ("t_triangle",   "三角波",   "ns=3;i=1006", "triangle",  {"min": -2, "max": 2, "period": 30}),

    # ========== self_add 自定义测点 (UASIM project) ==========
    ("t_flyash_pressure",    "飞灰压力",   "ns=3;i=1009", "random",     {"min": 0, "max": 1.0}),
    ("t_value_status",       "状态值",     "ns=3;i=1010", "constant",   {"value": 0}),
    ("t_ashpump_leverl",     "灰泵液位1",  "ns=3;i=1011", "square",     {"min": 0, "max": 100, "period": 8}),
    ("t_flyash_level",       "飞灰液位",   "ns=3;i=1012", "sinusoid",   {"min": 20, "max": 80, "period": 30}),
    ("t_ashbin_level",       "灰库液位",   "ns=3;i=1013", "random",     {"min": 10, "max": 90}),
    ("t_ashpump_level",      "灰泵液位2",  "ns=3;i=1014", "square",     {"min": 0, "max": 100, "period": 8}),
    ("t_compressor_pressure","压缩机压力", "ns=3;i=1015", "square",     {"min": 0, "max": 1.6, "period": 8}),

    # ========== 智慧输灰高级模块 - 新增测点 ==========

    # ---- 锅炉侧 ----
    ("t_boiler_load",        "锅炉负荷",   "ns=3;i=2001", "load_core",  {
        "night_min": 42, "night_max": 52,
        "morning_peak": 92, "midday_dip": 68,
        "afternoon_peak": 90, "evening_min": 48,
        "noise": 2.0, "inertia": 0.3
    }),
    ("t_flue_gas_volume",    "烟气量",     "ns=3;i=2002", "load_follow", {
        "base": 80, "coefficient": 2.2, "noise": 8,
        "unit": "kNm³/h"
    }),
    ("t_exhaust_temp",       "排烟温度",   "ns=3;i=2003", "load_follow", {
        "base": 110, "coefficient": 0.6, "noise": 3, "lag": 5,
        "unit": "°C"
    }),

    # ---- 除尘侧 ----
    ("t_dust_concentration", "粉尘排放浓度","ns=3;i=2004", "load_follow", {
        "base": 3, "coefficient": 0.25, "noise": 2, "lag": 10,
        "unit": "mg/Nm³"
    }),
    ("t_dust_diff_pressure", "除尘器压差", "ns=3;i=2005", "load_follow", {
        "base": 600, "coefficient": 10, "noise": 50, "lag": 15,
        "unit": "Pa"
    }),

    # ---- 输灰系统 ----
    ("t_convey_pressure",    "输送气压",   "ns=3;i=2006", "load_follow", {
        "base": 0.15, "coefficient": 0.005, "noise": 0.04,
        "unit": "MPa"
    }),
    ("t_hopper_ash_f1",      "#1电场灰量", "ns=3;i=2007", "hopper", {
        "base_rate": 2.0, "load_factor": 0.03, "noise": 0.3,
        "convey_rate": 1.5, "unit": "t/h"
    }),
    ("t_hopper_ash_f2",      "#2电场灰量", "ns=3;i=2008", "hopper", {
        "base_rate": 1.2, "load_factor": 0.02, "noise": 0.2,
        "convey_rate": 0.9, "unit": "t/h"
    }),
    ("t_hopper_ash_f3",      "#3电场灰量", "ns=3;i=2009", "hopper", {
        "base_rate": 0.6, "load_factor": 0.01, "noise": 0.1,
        "convey_rate": 0.5, "unit": "t/h"
    }),
    ("t_hopper_ash_f4",      "#4电场灰量", "ns=3;i=2010", "hopper", {
        "base_rate": 0.3, "load_factor": 0.005, "noise": 0.08,
        "convey_rate": 0.25, "unit": "t/h"
    }),
    ("t_convey_pipe_density","管道输灰浓度","ns=3;i=2011", "load_follow", {
        "base": 80, "coefficient": 1.5, "noise": 20,
        "unit": "g/m³"
    }),

    # ---- 空压机 ----
    ("t_air_compressor_current","空压机电流","ns=3;i=2012","load_follow", {
        "base": 35, "coefficient": 0.3, "noise": 5,
        "unit": "A"
    }),

    # ---- 能耗 ----
    ("t_energy_consumption", "系统能耗",   "ns=3;i=2013", "energy",     {
        "idle": 45, "load_factor": 1.2, "noise": 5,
        "unit": "kWh"
    }),
    ("t_convey_efficiency",  "输灰效率",   "ns=3;i=2014", "efficiency", {
        "base": 85, "noise": 3,
        "unit": "%"
    }),

    # ---- 设备状态 ----
    ("t_equipment_status",   "设备运行状态","ns=3;i=2015","equipment",  {
        "normal_status": 1, "fault_probability": 0.0005,
        "repair_time": 30, "unit": ""
    }),
    ("t_convey_speed",       "输灰速度",   "ns=3;i=2016", "load_follow", {
        "base": 5, "coefficient": 0.04, "noise": 0.3,
        "unit": "m/s"
    }),
    ("t_ash_temperature",    "灰温",       "ns=3;i=2017", "load_follow", {
        "base": 80, "coefficient": 0.8, "noise": 5, "lag": 8,
        "unit": "°C"
    }),
]

UNITS_FALLBACK: dict[str, str] = {
    "t_counter":               "",
    "t_random":                "",
    "t_sawtooth":              "",
    "t_sinusoid":              "",
    "t_square":                "",
    "t_triangle":              "",
    "t_flyash_pressure":       "kPa",
    "t_value_status":          "",
    "t_ashpump_leverl":        "%",
    "t_flyash_level":          "%",
    "t_ashbin_level":          "%",
    "t_ashpump_level":         "%",
    "t_compressor_pressure":   "MPa",
    "t_boiler_load":           "%",
    "t_flue_gas_volume":       "kNm³/h",
    "t_exhaust_temp":          "°C",
    "t_dust_concentration":    "mg/Nm³",
    "t_dust_diff_pressure":    "Pa",
    "t_convey_pressure":       "MPa",
    "t_hopper_ash_f1":         "t/h",
    "t_hopper_ash_f2":         "t/h",
    "t_hopper_ash_f3":         "t/h",
    "t_hopper_ash_f4":         "t/h",
    "t_convey_pipe_density":   "g/m³",
    "t_air_compressor_current":"A",
    "t_energy_consumption":    "kWh",
    "t_convey_efficiency":     "%",
    "t_equipment_status":      "",
    "t_convey_speed":          "m/s",
    "t_ash_temperature":       "°C",
}

# 测点工程单位 (如果 params 中有 unit 则优先使用)
POINT_UNITS: dict[str, str] = {}
for tbl, _, _, sim_type, params in POINTS:
    unit = params.get("unit", "")
    if not unit:
        unit = UNITS_FALLBACK.get(tbl, "")
    POINT_UNITS[tbl] = unit


# =============================================================================
# 告警阈值配置
# =============================================================================
# (测点名称, 低低限, 低限, 高限, 高高限, 描述)
ALERT_THRESHOLDS: list[tuple[str, float | None, float | None, float | None, float | None, str]] = [
    ("t_boiler_load",          None,  40.0,  95.0,  None,     "锅炉负荷异常"),
    ("t_exhaust_temp",         None,  120.0, 170.0, 185.0,    "排烟温度异常"),
    ("t_dust_concentration",   None,  None,  25.0,  30.0,     "粉尘排放超标"),
    ("t_dust_diff_pressure",   None,  500.0, 1800.0, 2200.0, "除尘器压差异常"),
    ("t_convey_pressure",      0.05,  0.10,  0.70,  0.85,     "输送气压异常"),
    ("t_ashbin_level",         None,  10.0,  85.0,  95.0,     "灰库液位异常"),
    ("t_air_compressor_current",None, 30.0,  75.0,  85.0,     "空压机电流异常"),
    ("t_equipment_status",     None,  None,  None,  None,     "设备故障"),
    ("t_convey_efficiency",    None,  70.0,  None,  None,     "输灰效率偏低"),
]


# =============================================================================
# 专家知识库 (故障诊断规则)
# =============================================================================
# 每个规则: (规则名称, 条件列表, 诊断结论, 建议措施, 故障类型)
# 条件: (测点名, 比较器, 阈值)
# 比较器: "lt"(<), "gt"(>), "lte"(<=), "gte"(>=), "eq"(==), "neq"(!=)
EXPERT_RULES: list[tuple[str, list[tuple[str, str, float]], str, str, str]] = [
    (
        "空压机过载",
        [("t_air_compressor_current", "gt", 80.0)],
        "空压机电流过高，可能机械卡涩或电气故障",
        "检查空压机运行声音、电流波动，排查电气回路；若持续超限需切换备用空压机",
        "电气故障",
    ),
    (
        "输灰管道堵塞预警",
        [("t_convey_pressure", "gt", 0.75), ("t_convey_pipe_density", "gt", 250)],
        "输送气压偏高且浓度大，输灰管道可能堵塞",
        "检查输灰管道压力波动，启动反吹扫程序；若持续高压力需人工巡检",
        "机械本体故障",
    ),
    (
        "输灰管道泄漏预警",
        [("t_convey_pressure", "lt", 0.10), ("t_convey_speed", "gt", 8.0)],
        "输送气压偏低且速度偏高，管道可能泄漏",
        "检查输灰管道沿线是否有漏灰点，压缩空气系统是否正常",
        "机械本体故障",
    ),
    (
        "除尘器压差高",
        [("t_dust_diff_pressure", "gt", 2000.0)],
        "除尘器压差异常升高，滤袋可能堵塞或破损",
        "检查除尘器清灰系统是否正常，是否需要增加喷吹频率；检查滤袋状况",
        "运行工况故障",
    ),
    (
        "粉尘排放超标",
        [("t_dust_concentration", "gt", 25.0)],
        "粉尘排放浓度偏高，可能存在滤袋破损或除尘效率下降",
        "检查除尘器出口排放，排查滤袋破损情况；检查电场运行参数",
        "运行工况故障",
    ),
    (
        "排烟温度过高",
        [("t_exhaust_temp", "gt", 180.0)],
        "排烟温度过高，可能影响除尘器安全和效率",
        "检查锅炉燃烧工况，调整配风；检查空预器换热效率",
        "运行工况故障",
    ),
    (
        "灰库高料位预警",
        [("t_ashbin_level", "gt", 90.0)],
        "灰库料位过高，有满库风险",
        "加大输灰系统出库频率，联系灰渣综合利用单位加快拉灰",
        "运行工况故障",
    ),
    (
        "输灰效率偏低",
        [("t_convey_efficiency", "lt", 70.0)],
        "输灰效率低于正常水平，系统运行不经济",
        "优化输灰周期参数，检查输灰管道阻力；低负荷时可降低输送气压",
        "运行工况故障",
    ),
    (
        "锅炉低负荷运行",
        [("t_boiler_load", "lt", 45.0)],
        "锅炉处于低负荷运行状态，建议优化输灰运行方式",
        "适当降低输灰频率和输送气压，减少空压机运行台数，实现节能运行",
        "运行工况故障",
    ),
    (
        "综合故障: 设备停运",
        [("t_equipment_status", "eq", 0)],
        "设备处于停运状态",
        "检查设备启停记录，确认是否为计划停机；如为非计划停机请检查故障原因",
        "电气故障",
    ),
]


# =============================================================================
# 优化方案模板
# =============================================================================
OPTIMIZATION_PLANS: list[dict[str, Any]] = [
    {
        "id": "PLAN-EC-001",
        "name": "低负荷节能运行方案",
        "condition": "t_boiler_load < 50%",
        "actions": [
            "降低输送气压至 0.25-0.35 MPa",
            "减少空压机运行数量至 1 台",
            "延长输灰周期至 15-20 分钟",
            "关闭非必要输灰支路",
        ],
        "expected_saving": "15-25% 能耗降低",
        "risk": "低",
    },
    {
        "id": "PLAN-EC-002",
        "name": "中负荷经济运行方案",
        "condition": "50% ≤ t_boiler_load < 75%",
        "actions": [
            "维持输送气压 0.35-0.50 MPa",
            "空压机运行 1-2 台",
            "输灰周期 10-15 分钟",
            "根据灰斗灰量动态调整输灰频率",
        ],
        "expected_saving": "5-10% 能耗降低",
        "risk": "低",
    },
    {
        "id": "PLAN-EC-003",
        "name": "高负荷保产运行方案",
        "condition": "t_boiler_load ≥ 75%",
        "actions": [
            "提高输送气压至 0.50-0.65 MPa",
            "空压机运行 2 台",
            "缩短输灰周期至 5-10 分钟",
            "全部输灰支路投入运行",
            "密切监视灰斗灰量和除尘器压差",
        ],
        "expected_saving": "保障输灰能力为首要目标",
        "risk": "中",
    },
    {
        "id": "PLAN-FAULT-001",
        "name": "输灰管道堵塞处理方案",
        "condition": "convey_pressure > 0.75 AND pipe_density > 250",
        "actions": [
            "立即启动管道反吹扫",
            "若反吹无效，逐段检查管道",
            "必要时切换备用输灰管道",
            "清理堵塞段后恢复正常运行",
        ],
        "expected_saving": "避免停运损失",
        "risk": "高",
    },
    {
        "id": "PLAN-ENV-001",
        "name": "粉尘排放超标处理方案",
        "condition": "dust_concentration > 25 mg/Nm³",
        "actions": [
            "增加除尘器喷吹频率",
            "检查并调整电场参数 (电压、电流)",
            "排查滤袋破损情况，必要时隔离故障仓室",
            "通知运维人员现场检查",
        ],
        "expected_saving": "确保环保排放达标",
        "risk": "高",
    },
]


# =============================================================================
# 告警严重级别
# =============================================================================
ALERT_LEVELS: dict[str, int] = {
    "FATAL":   4,  # 危险 - 立即处理
    "CRITICAL": 3,  # 严重 - 需尽快处理
    "WARNING":  2,  # 警告 - 关注
    "INFO":     1,  # 提示 - 信息
}
