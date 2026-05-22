"""
智慧输灰高级模块 - 一体化应用入口
====================================
模拟采集 + Web 服务合并为一个进程。
"""

import threading

from app import app
from collector import create_collector, run_collector_loop
from settings import WEB_HOST, WEB_PORT, WEB_DEBUG, MODE


def main() -> None:
    print("=" * 60)
    print(f"  智慧输灰高级模块 - 服务启动")
    print(f"  {'=' * 60}")
    print(f"  运行模式: {MODE}")
    print(f"  Web 访问: http://{WEB_HOST}:{WEB_PORT}")
    print(f"  Ctrl+C 停止")

    # 后台采集线程
    collector = create_collector()
    t = threading.Thread(target=run_collector_loop, args=(collector,), daemon=True)
    t.start()

    # Flask Web 服务
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG, use_reloader=False)


if __name__ == "__main__":
    main()
