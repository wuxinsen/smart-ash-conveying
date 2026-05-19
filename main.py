"""
智慧输灰高级模块 - 一体化应用
================================
模拟采集 + Web 服务合并为一个进程
"""

import taos
import time
import threading
from datetime import datetime

from config import POINTS, POINT_UNITS
from simulator import PowerPlantSimulator, init_database, insert_alert_if_needed
from app import app

# 编码适配: Windows GBK 终端兼容
import builtins
_orig_print = builtins.print
def _ps(*args, **kwargs) -> None:
    text = " ".join(str(a) for a in args)
    try:
        _orig_print(text, **kwargs)
    except UnicodeEncodeError:
        _orig_print(text.encode("gbk", errors="replace").decode("gbk", errors="replace"), **kwargs)


def insert_points_batch(cursor, ts: datetime, results: dict[str, float], quality: int) -> None:
    """批量插入所有测点数据 (单条多表 INSERT)。"""
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    parts = []
    for tbl, _tag, _nid, _st, _p in POINTS:
        v = results.get(tbl, 0.0)
        unit = POINT_UNITS.get(tbl, "")
        parts.append(
            f"ash_system.{tbl} (ts, val, unit, quality) "
            f"VALUES ('{ts_str}', {v}, '{unit}', {quality})"
        )
    cursor.execute(f"INSERT INTO {' '.join(parts)}")


def run_simulator() -> None:
    """后台模拟采集线程：每秒生成并写入测点数据。"""
    INTERVAL = 1.0
    QUALITY_GOOD = 192
    ALERT_CHECK_INTERVAL = 10

    conn = taos.connect(host="localhost", port=6030, user="root", password="taosdata")
    cursor = conn.cursor()

    try:
        init_database(cursor)
        plant = PowerPlantSimulator()
        alert_counter = 0

        header = (f"{'时间':<20} {'负荷%':>6} {'烟气(kNm³/h)':>12} "
                  f"{'粉尘(mg)':>10} {'气压(MPa)':>10} {'能耗(kWh)':>10} "
                  f"{'效率%':>7} {'状态':>6}")
        _ps(f"\n  {'=' * len(header)}")
        _ps(f"  {header}")
        _ps(f"  {'=' * len(header)}")

        while True:
            now = datetime.now()
            results = plant.step(INTERVAL)

            # 批量写入 (1 条 INSERT 写入所有测点)
            insert_points_batch(cursor, now, results, QUALITY_GOOD)

            alert_counter += INTERVAL
            if alert_counter >= ALERT_CHECK_INTERVAL:
                insert_alert_if_needed(cursor, now, results)
                alert_counter = 0

            conn.commit()

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
                f"{load:>6.1f}{flue:>12.1f}{dust:>10.2f}{convey_p:>10.3f}"
                f"{energy:>10.1f}{eff:>7.1f}{status_str:>6}{saving_mark}"
            )
            time.sleep(INTERVAL)

    except Exception:
        _ps("\n[错误] 模拟器异常退出")
        import traceback
        traceback.print_exc()
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
        _ps("[OK] 模拟器连接已关闭。")


if __name__ == "__main__":
    _ps("=" * 60)
    _ps("  智慧输灰高级模块 - 一体化服务")
    _ps("=" * 60)
    _ps("  TDengine: localhost:6030/ash_system")
    _ps("  访问地址: http://localhost:5000")
    _ps("  Ctrl+C 停止服务")
    _ps("=" * 60)

    t = threading.Thread(target=run_simulator, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
