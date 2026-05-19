"""
智慧输灰高级模块 - 模拟数据采集引擎 v2.0
===========================================
模拟 #3 机组电厂输灰系统全量测点数据，存入 TDengine (ash_system)
实现锅炉负荷联动、设备状态仿真、能耗跟踪等功能
"""

import taos
import time
import math
import random
from datetime import datetime, timedelta
from typing import Any


# 编码适配: Windows GBK 终端兼容
import builtins
_orig_print = builtins.print
def _ps(*args, **kwargs) -> None:
    """安全打印，自动处理编码问题。"""
    text = " ".join(str(a) for a in args)
    try:
        _orig_print(text, **kwargs)
    except UnicodeEncodeError:
        _orig_print(text.encode("gbk", errors="replace").decode("gbk", errors="replace"), **kwargs)

from config import POINTS, POINT_UNITS, ALERT_THRESHOLDS


# =============================================================================
# 电厂模拟引擎
# =============================================================================

class PowerPlantSimulator:
    """
    电厂运行模拟器
    核心逻辑: 锅炉负荷驱动 → 各参数联动 → 设备状态影响
    """

    def __init__(self) -> None:
        # 时间 (秒, 一天内)
        self.sim_time: float = 0.0

        # 锅炉负荷 (%)
        self.load_target: float = 70.0
        self.load_actual: float = 70.0
        self.load_display: float = 70.0

        # 设备状态
        self.equipment_running: bool = True
        self.fault_active: bool = False
        self.fault_timer: float = 0.0
        self.fault_duration: float = 0.0

        # 灰斗累积量
        self.hopper_accum: dict[str, float] = {}

        # 能耗累积
        self.energy_total: float = 0.0

        # 故障标志 (用于触发联锁)
        self.convey_blocked: bool = False

        # 节能模式
        self.energy_saving: bool = False

    def _load_profile(self, t: float) -> float:
        """
        日负荷曲线 (t: 秒, 0-86400)
        典型日负荷:
          00:00-05:00  深夜低谷  42-52%
          05:00-08:00  早上升峰  52→92%
          08:00-12:00  上午高峰  85-92%
          12:00-14:00  中午低谷  68-75%
          14:00-18:00  下午高峰  80-90%
          18:00-22:00  晚间下降  75→55%
          22:00-24:00  夜间下降  55→42%
        """
        hour = (t / 3600) % 24

        if hour < 5:
            # 深夜低谷 (0-5点)
            v = 47 + 5 * math.sin(hour / 5 * math.pi)
        elif hour < 8:
            # 早上升峰 (5-8点)
            ratio = (hour - 5) / 3
            v = 47 + 45 * ratio
        elif hour < 12:
            # 上午高峰 (8-12点)
            v = 88 + 4 * math.sin((hour - 8) / 4 * math.pi)
        elif hour < 14:
            # 中午低谷 (12-14点)
            ratio = (hour - 12) / 2
            v = 92 - 24 * ratio
        elif hour < 18:
            # 下午高峰 (14-18点)
            ratio = (hour - 14) / 4
            v = 68 + 22 * ratio
        elif hour < 22:
            # 晚间下降 (18-22点)
            ratio = (hour - 18) / 4
            v = 90 - 35 * ratio
        else:
            # 夜间下降 (22-24点)
            ratio = (hour - 22) / 2
            v = 55 - 13 * ratio

        return v

    def step(self, dt: float) -> dict[str, float]:
        """
        推进仿真一步，返回所有测点的当前值
        dt: 时间步长 (秒)
        """
        self.sim_time += dt
        t = self.sim_time

        # ---- 1. 锅炉负荷 ----
        base_load = self._load_profile(t)
        noise = random.gauss(0, 1.5)
        self.load_target = base_load + noise
        # 惯性滤波
        self.load_actual += (self.load_target - self.load_actual) * 0.3
        self.load_display = max(35.0, min(100.0, self.load_actual))
        load = self.load_display

        # ---- 2. 设备状态 ----
        if not self.fault_active:
            # 随机故障
            if random.random() < 0.0003:
                self.fault_active = True
                self.fault_timer = 0.0
                self.fault_duration = random.uniform(20, 60)
                self.equipment_running = False
        elif self.fault_active:
            self.fault_timer += dt
            if self.fault_timer >= self.fault_duration:
                self.fault_active = False
                self.equipment_running = True

        equipment_status = 1 if self.equipment_running else (2 if self.fault_active else 0)

        # 故障时自动停止输送
        self.convey_blocked = self.fault_active or (load < 40)

        # 节能模式
        self.energy_saving = load < 55 and self.equipment_running

        # ---- 3. 生成所有测点值 ----
        results: dict[str, float] = {}

        for tbl, _tag_name, _node_id, sim_type, params in POINTS:
            results[tbl] = self._generate(tbl, sim_type, params, load, dt)

        # 特殊处理: equipment_status 由内部状态决定
        results["t_equipment_status"] = float(equipment_status)

        return results

    def _generate(self, tbl: str, sim_type: str, params: dict[str, Any],
                  load: float, dt: float) -> float:
        """根据类型生成单点值"""
        if sim_type == "counter":
            v = self._get_state(tbl, float(params.get("min", 0)))
            v += params.get("step", 1)
            if v > params.get("max", 30):
                v = float(params.get("min", 0))
            self._set_state(tbl, v)
            return v
        elif sim_type == "random":
            return random.uniform(params["min"], params["max"])
        elif sim_type == "sinusoid":
            p = self._get_state(tbl, 0.0)
            amp = (params["max"] - params["min"]) / 2
            off = (params["max"] + params["min"]) / 2
            period = params.get("period", 30)
            self._set_state(tbl, p + 2 * math.pi * dt / period)
            return off + amp * math.sin(p)
        elif sim_type == "sawtooth":
            p = self._get_state(tbl, 0.0)
            period = params.get("period", 10)
            ratio = (p % period) / period
            self._set_state(tbl, p + dt)
            return params["min"] + (params["max"] - params["min"]) * ratio
        elif sim_type == "triangle":
            p = self._get_state(tbl, 0.0)
            period = params.get("period", 30)
            t_val = p % period
            half = period / 2
            ratio = t_val / half if t_val <= half else (period - t_val) / half
            self._set_state(tbl, p + dt)
            return params["min"] + (params["max"] - params["min"]) * ratio
        elif sim_type == "square":
            p = self._get_state(tbl, 0.0)
            period = params.get("period", 20)
            t_val = p % period
            self._set_state(tbl, p + dt)
            return params["max"] if t_val < period / 2 else params["min"]
        elif sim_type == "constant":
            return float(params.get("value", 0))
        elif sim_type == "load_core":
            return max(35.0, min(100.0, load + random.gauss(0, params.get("noise", 1))))
        elif sim_type == "load_follow":
            base = params["base"]
            coeff = params.get("coefficient", 1)
            noise_amp = params.get("noise", 1)
            lag = params.get("lag", 0)
            raw = base + coeff * (load - 50) + random.gauss(0, noise_amp)
            if lag > 0:
                prev = self._get_state(tbl + "_filtered", raw)
                alpha = 1.0 / (lag + 1)
                filtered = prev + alpha * (raw - prev)
                self._set_state(tbl + "_filtered", filtered)
                return max(0, filtered)
            return max(0, raw)
        elif sim_type == "hopper":
            base_rate = params["base_rate"]
            load_factor = params.get("load_factor", 0.01)
            noise_amp = params.get("noise", 0.1)
            convey_rate = params.get("convey_rate", 1.0)
            ash_rate = base_rate + load_factor * load + random.gauss(0, noise_amp)
            ash_amount = ash_rate * dt / 3600
            accum = self.hopper_accum.get(tbl, 0.5)
            accum += ash_amount
            should_convey = (self.sim_time % 60) < dt
            if should_convey and self.equipment_running and not self.convey_blocked:
                convey_this = convey_rate * 5 / 3600
                accum = max(0, accum - convey_this)
            self.hopper_accum[tbl] = accum
            return max(0, accum)
        elif sim_type == "energy":
            idle = params["idle"]
            load_factor = params.get("load_factor", 1)
            noise_amp = params.get("noise", 2)
            raw = idle + load_factor * (load - 40) + random.gauss(0, noise_amp)
            if self.energy_saving:
                raw *= 0.7
            if not self.equipment_running:
                raw *= 0.2
            return max(10, raw)
        elif sim_type == "efficiency":
            base = params["base"]
            noise_amp = params.get("noise", 2)
            load_factor = max(0.7, min(1.1, (load - 30) / 50))
            eff = base * load_factor + random.gauss(0, noise_amp)
            if not self.equipment_running:
                eff *= 0.3
            return max(30, min(100, eff))
        elif sim_type == "equipment":
            return 1.0
        else:
            return 0.0

    def _get_state(self, key: str, default: float = 0.0) -> float:
        return getattr(self, "_state_" + key, default)

    def _set_state(self, key: str, value: float) -> None:
        setattr(self, "_state_" + key, value)


# =============================================================================
# TDengine 数据操作
# =============================================================================

TaosCursor = Any


def create_stable_alerts(cursor: TaosCursor) -> None:
    """创建告警事件超级表及子表。"""
    cursor.execute(
        "CREATE STABLE IF NOT EXISTS alert_events ("
        "  ts TIMESTAMP,"
        "  alert_level INT,"
        "  alert_level_name BINARY(16),"
        "  source_tag BINARY(64),"
        "  source_value DOUBLE,"
        "  alert_message BINARY(256),"
        "  suggested_action BINARY(256)"
        ") TAGS ("
        "  unit_name BINARY(64)"
        ");"
    )
    # 创建子表
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS ae_unit3 "
        "USING ash_system.alert_events TAGS('#3机组输灰系统');"
    )


def init_database(cursor: TaosCursor) -> None:
    """初始化数据库和所有表。"""
    cursor.execute(
        "CREATE DATABASE IF NOT EXISTS ash_system "
        "KEEP 30 DURATION 1 BUFFER 256;"
    )
    cursor.execute("USE ash_system;")
    cursor.execute(
        "CREATE STABLE IF NOT EXISTS tag_data ("
        "  ts TIMESTAMP,"
        "  val DOUBLE,"
        "  unit BINARY(32),"
        "  quality INT"
        ") TAGS ("
        "  tag_name BINARY(64),"
        "  node_id BINARY(128)"
        ");"
    )
    create_stable_alerts(cursor)

    # 创建所有测点子表
    for tbl, tag_name, node_id, _, _ in POINTS:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS ash_system.{tbl} "
            f"USING ash_system.tag_data TAGS('{tag_name}', '{node_id}');"
        )

    _ps(f"[OK] 数据库 ash_system 就绪，共 {len(POINTS)} 个测点子表 + 告警表。")


def insert_point(cursor: TaosCursor, tbl: str, ts: datetime, value: float, quality: int) -> None:
    """插入一条测点数据。"""
    unit = POINT_UNITS.get(tbl, "")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    cursor.execute(
        f"INSERT INTO ash_system.{tbl} (ts, val, unit, quality) "
        f"VALUES ('{ts_str}', {value}, '{unit}', {quality});"
    )


def insert_alert(cursor: TaosCursor, ts: datetime, level: int, level_name: str,
                 source_tag: str, source_value: float, message: str, action: str) -> None:
    """插入一条告警记录。"""
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    unit_name = "#3机组输灰系统"
    cursor.execute(
        f"INSERT INTO ash_system.ae_unit3 "
        f"(ts, alert_level, alert_level_name, source_tag, source_value, "
        f" alert_message, suggested_action) "
        f"VALUES ('{ts_str}', {level}, '{level_name}', '{source_tag}', "
        f" {source_value}, '{message}', '{action}');"
    )


def insert_alert_if_needed(cursor: TaosCursor, ts: datetime,
                           values: dict[str, float]) -> None:
    """检查所有阈值，超限则写入告警 (仅触发最严重级别)。"""
    for tag, lo_lo, lo, hi, hi_hi, desc in ALERT_THRESHOLDS:
        if tag not in values:
            continue
        v = values[tag]
        if tag == "t_equipment_status" and v == 0:
            insert_alert(cursor, ts, 3, "CRITICAL", tag, v,
                         "设备停运", "检查启停记录，如非计划停机请排查故障原因")
        elif lo_lo is not None and v < lo_lo:
            insert_alert(cursor, ts, 4, "FATAL", tag, v,
                         f"{desc}: 值 {v:.2f} 低于低低限 {lo_lo}", "紧急处理!")
        elif hi_hi is not None and v > hi_hi:
            insert_alert(cursor, ts, 4, "FATAL", tag, v,
                         f"{desc}: 值 {v:.2f} 高于高高限 {hi_hi}", "紧急处理!")
        elif lo is not None and v < lo:
            insert_alert(cursor, ts, 2, "WARNING", tag, v,
                         f"{desc}: 值 {v:.2f} 低于下限 {lo}", "关注并分析原因")
        elif hi is not None and v > hi:
            insert_alert(cursor, ts, 2, "WARNING", tag, v,
                         f"{desc}: 值 {v:.2f} 高于上限 {hi}", "关注并分析原因")


# =============================================================================
# 主程序
# =============================================================================

def main() -> None:
    INTERVAL = 1.0        # 采集周期 (秒)
    QUALITY_GOOD = 192     # OPC UA 质量码 Good
    ALERT_CHECK_INTERVAL = 10  # 告警检查间隔 (秒)

    _ps("=" * 68)
    _ps("  智慧输灰高级模块 v2.0 - #3机组模拟数据采集系统")
    _ps("  数据库: ash_system (TDengine)")
    _ps(f"  采集间隔: {INTERVAL}s | 总测点数: {len(POINTS)}")
    _ps("=" * 68)

    conn = taos.connect(host="localhost", port=6030, user="root", password="taosdata")
    cursor = conn.cursor()
    _ps("[OK] 已连接到 TDengine。")

    # 初始化库表
    init_database(cursor)

    # 模拟引擎
    plant = PowerPlantSimulator()
    alert_counter = 0

    # -- 打印标题 --
    key_tags = [
        "t_boiler_load", "t_flue_gas_volume", "t_dust_concentration",
        "t_convey_pressure", "t_energy_consumption", "t_convey_efficiency",
        "t_equipment_status",
    ]
    header = f"{'时间':<20} {'负荷%':>6} {'烟气(kNm³/h)':>12} {'粉尘(mg)':>10} {'气压(MPa)':>10} {'能耗(kWh)':>10} {'效率%':>7} {'状态':>6}"
    _ps(f"\n  {'=' * len(header)}")
    _ps(f"  {header}")
    _ps(f"  {'=' * len(header)}")

    try:
        while True:
            now = datetime.now()

            # 仿真步进
            results = plant.step(INTERVAL)

            # 写入 TDengine
            for tbl, _tag, _nid, _st, _p in POINTS:
                v = results.get(tbl, 0.0)
                insert_point(cursor, tbl, now, v, QUALITY_GOOD)

            # 告警检查
            alert_counter += INTERVAL
            if alert_counter >= ALERT_CHECK_INTERVAL:
                insert_alert_if_needed(cursor, now, results)
                alert_counter = 0

            conn.commit()

            # -- 关键参数面板 --
            load = results.get("t_boiler_load", 0)
            flue = results.get("t_flue_gas_volume", 0)
            dust = results.get("t_dust_concentration", 0)
            convey_p = results.get("t_convey_pressure", 0)
            energy = results.get("t_energy_consumption", 0)
            eff = results.get("t_convey_efficiency", 0)
            status = results.get("t_equipment_status", 1)

            status_str = {1: "运行", 0: "停止", 2: "故障"}.get(int(status), "?")
            saving_mark = " [节能]" if plant.energy_saving else "      "

            _ps(
                f"  {now.strftime('%H:%M:%S'):<20}"
                f"{load:>6.1f}"
                f"{flue:>12.1f}"
                f"{dust:>10.2f}"
                f"{convey_p:>10.3f}"
                f"{energy:>10.1f}"
                f"{eff:>7.1f}"
                f"{status_str:>6}{saving_mark}"
            )

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        _ps("\n\n[停止] 用户中断。")
    except Exception as e:
        _ps(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        _ps("[OK] 连接已关闭。")


if __name__ == "__main__":
    main()
