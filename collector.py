"""
智慧输灰高级模块 - 统一数据采集层
====================================
提供 DataCollector 接口，支持模拟器和 OPC UA 两种实现。
上层代码不关心数据来源，只需要调 collect()。
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from config import POINTS
from database import insert_batch, check_and_insert_alerts, init_database
from settings import (
    MODE, QUALITY_GOOD, ALERT_CHECK_INTERVAL,
    OPC_URL, OPC_TIMEOUT,
)


# =============================================================================
# 抽象接口
# =============================================================================

class DataCollector(ABC):
    """数据采集器基类。所有采集器实现这个接口。"""

    @abstractmethod
    def connect(self) -> None:
        """建立连接。"""
        ...

    @abstractmethod
    def collect(self) -> dict[str, float]:
        """采集一轮所有测点，返回 {表名: 值}。"""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接。"""
        ...


# =============================================================================
# 模拟器实现
# =============================================================================

class SimulatorCollector(DataCollector):
    """使用 PowerPlantSimulator 产生模拟数据。"""

    def __init__(self) -> None:
        from simulator import PowerPlantSimulator
        self.sim = PowerPlantSimulator()

    def connect(self) -> None:
        print("[采集] 模拟器模式启动")

    def collect(self) -> dict[str, float]:
        return self.sim.step(1.0)

    def disconnect(self) -> None:
        print("[采集] 模拟器停止")


# =============================================================================
# OPC UA 实现（上线后使用）
# =============================================================================

class OpcuaCollector(DataCollector):
    """通过 OPC UA 从 DCS 采集真实数据。"""

    def __init__(self) -> None:
        self.client = None
        self.node_map: dict[str, Any] = {}  # {表名: Node对象}

    def connect(self) -> None:
        from opcua import Client
        self.client = Client(OPC_URL, timeout=OPC_TIMEOUT)
        self.client.connect()
        # 建立测点映射
        for tbl, _, node_id, _, _ in POINTS:
            try:
                self.node_map[tbl] = self.client.get_node(node_id)
            except Exception as e:
                print(f"[OPC UA] 警告: 无法找到节点 {tbl} ({node_id}): {e}")
        print(f"[OPC UA] 已连接 {OPC_URL}，{len(self.node_map)} 个测点就绪")

    def collect(self) -> dict[str, float]:
        results = {}
        for tbl, node in self.node_map.items():
            try:
                results[tbl] = float(node.get_value())
            except Exception:
                pass  # 读失败的测点跳过
        return results

    def disconnect(self) -> None:
        if self.client:
            self.client.disconnect()
            print("[OPC UA] 已断开")


# =============================================================================
# 工厂函数
# =============================================================================

def create_collector() -> DataCollector:
    """根据配置创建相应的采集器。"""
    if MODE == "live":
        return OpcuaCollector()
    else:
        return SimulatorCollector()


# =============================================================================
# 采集主循环
# =============================================================================

def run_collector_loop(collector: DataCollector | None = None) -> None:
    """
    采集主循环：采集 → 写入 DB → 检查告警。
    可在独立线程中运行。
    """
    if collector is None:
        collector = create_collector()

    init_database()
    collector.connect()

    alert_counter = 0
    try:
        while True:
            now = datetime.now()
            results = collector.collect()

            if results:
                insert_batch(results, now, QUALITY_GOOD)

                alert_counter += 1
                if alert_counter >= ALERT_CHECK_INTERVAL:
                    check_and_insert_alerts(now, results)
                    alert_counter = 0

            time.sleep(1.0)

    except KeyboardInterrupt:
        pass
    finally:
        collector.disconnect()


if __name__ == "__main__":
    run_collector_loop()
