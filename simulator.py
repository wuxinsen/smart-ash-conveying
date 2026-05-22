"""
智慧输灰高级模块 - 模拟数据采集引擎 v2.0
===========================================
PowerPlantSimulator — 电厂运行模拟器
核心逻辑: 锅炉负荷驱动 → 各参数联动 → 设备状态影响
"""

import math
import random
from typing import Any

from config import POINTS


class PowerPlantSimulator:
    """
    电厂运行模拟器。
    只负责生成模拟数据，不关心数据库写入。
    使用: results = simulator.step(1.0)
    """

    def __init__(self) -> None:
        self.sim_time: float = 0.0
        self.load_target: float = 70.0
        self.load_actual: float = 70.0
        self.load_display: float = 70.0
        self.equipment_running: bool = True
        self.fault_active: bool = False
        self.fault_timer: float = 0.0
        self.fault_duration: float = 0.0
        self.hopper_accum: dict[str, float] = {}
        self.energy_total: float = 0.0
        self.convey_blocked: bool = False
        self.energy_saving: bool = False

    def _load_profile(self, t: float) -> float:
        """日负荷曲线 (t: 秒, 0-86400)。"""
        hour = (t / 3600) % 24
        if hour < 5:
            v = 47 + 5 * math.sin(hour / 5 * math.pi)
        elif hour < 8:
            v = 47 + 45 * (hour - 5) / 3
        elif hour < 12:
            v = 88 + 4 * math.sin((hour - 8) / 4 * math.pi)
        elif hour < 14:
            v = 92 - 24 * (hour - 12) / 2
        elif hour < 18:
            v = 68 + 22 * (hour - 14) / 4
        elif hour < 22:
            v = 90 - 35 * (hour - 18) / 4
        else:
            v = 55 - 13 * (hour - 22) / 2
        return v

    def step(self, dt: float) -> dict[str, float]:
        """推进仿真一步，返回 {表名: 值}。"""
        self.sim_time += dt
        t = self.sim_time
        base_load = self._load_profile(t)
        self.load_target = base_load + random.gauss(0, 1.5)
        self.load_actual += (self.load_target - self.load_actual) * 0.3
        self.load_display = max(35.0, min(100.0, self.load_actual))
        load = self.load_display

        if not self.fault_active:
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
        self.convey_blocked = self.fault_active or (load < 40)
        self.energy_saving = load < 55 and self.equipment_running

        results: dict[str, float] = {}
        for tbl, _tag_name, _node_id, sim_type, params in POINTS:
            results[tbl] = self._generate(tbl, sim_type, params, load, dt)
        results["t_equipment_status"] = float(equipment_status)
        return results

    def _generate(self, tbl: str, sim_type: str, params: dict[str, Any],
                  load: float, dt: float) -> float:
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
                accum = max(0, accum - convey_rate * 5 / 3600)
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
        return 0.0

    def _get_state(self, key: str, default: float = 0.0) -> float:
        return getattr(self, "_state_" + key, default)

    def _set_state(self, key: str, value: float) -> None:
        setattr(self, "_state_" + key, value)
