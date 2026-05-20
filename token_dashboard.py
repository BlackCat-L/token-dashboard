#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Claude Code Token 用量可视化面板 v6 — OOP 重构版"""
import os, http.server, threading

from scanner import SessionStore
from cost import Pricing, CostCalculator
from analytics import TipsEngine, Aggregator
from dashboard_html import HTMLBuilder

PORT = 8766


def main():
    pricing = Pricing()
    calculator = CostCalculator(pricing)

    store = SessionStore(pricing_callback=calculator.cost_callback)

    from scanner import BASE_DIR
    print(f"扫描 {BASE_DIR} ...")
    projects = store.scan_all()
    print(f"发现 {len(projects)} 个项目")
    for p in projects:
        print(f"  {p['name']}: {p['sessions']} 会话, {p['total']/1e6:.1f}M tokens")

    builder = HTMLBuilder(pricing)
    html = builder.build(projects)
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n面板: http://127.0.0.1:{PORT}/token_dashboard.html ({len(html)} bytes)")

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    url = f"http://127.0.0.1:{PORT}/token_dashboard.html"
    threading.Timer(1.0, lambda: _open_browser(url)).start()

    server = http.server.HTTPServer(("0.0.0.0", PORT), http.server.SimpleHTTPRequestHandler)
    print(f"服务已启动: {url}  (Ctrl+C 退出)")
    server.serve_forever()


def _open_browser(url):
    os.startfile(url)  # Windows: 系统默认浏览器


if __name__ == "__main__":
    main()
