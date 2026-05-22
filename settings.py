"""
智慧输灰高级模块 - 环境配置
=============================
所有环境相关的配置集中在这里，通过环境变量或配置文件加载。
"""

import os
from pathlib import Path

# 运行模式: "simulator" = 使用模拟数据, "live" = 连接真实 DCS
MODE = os.getenv("ASH_MODE", "simulator")

# ---------------------------------------------------------------------------
# TDengine 连接
# ---------------------------------------------------------------------------
TD_HOST = os.getenv("ASH_TD_HOST", "localhost")
TD_PORT = int(os.getenv("ASH_TD_PORT", "6030"))
TD_USER = os.getenv("ASH_TD_USER", "root")
TD_PASS = os.getenv("ASH_TD_PASS", "taosdata")
TD_DB   = os.getenv("ASH_TD_DB", "ash_system")

# ---------------------------------------------------------------------------
# OPC UA 连接 (live 模式使用)
# ---------------------------------------------------------------------------
OPC_URL = os.getenv("ASH_OPC_URL", "opc.tcp://localhost:4840")
OPC_TIMEOUT = int(os.getenv("ASH_OPC_TIMEOUT", "10"))  # 连接超时(秒)
OPC_INTERVAL = float(os.getenv("ASH_OPC_INTERVAL", "1.0"))  # 采集周期(秒)

# ---------------------------------------------------------------------------
# Web 服务
# ---------------------------------------------------------------------------
WEB_HOST = os.getenv("ASH_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("ASH_WEB_PORT", "5000"))
WEB_DEBUG = os.getenv("ASH_WEB_DEBUG", "false").lower() == "true"

# ---------------------------------------------------------------------------
# 系统参数
# ---------------------------------------------------------------------------
ALERT_CHECK_INTERVAL = int(os.getenv("ASH_ALERT_INTERVAL", "10"))  # 告警检查间隔(秒)
QUALITY_GOOD = 192  # OPC UA 质量码

# ---------------------------------------------------------------------------
# 加载本地覆盖 (settings_local.py 不提交到 Git)
# ---------------------------------------------------------------------------
_local = Path(__file__).parent / "settings_local.py"
if _local.exists():
    exec(_local.read_text(encoding="utf-8"))
