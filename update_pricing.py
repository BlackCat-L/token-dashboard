#!/usr/bin/env python3
"""DeepSeek API 价格同步脚本 —— 从官网抓取最新定价，更新 pricing.json"""
import json, re, sys, os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRICING_FILE = os.path.join(SCRIPT_DIR, "pricing.json")
PRICING_URL = "https://api-docs.deepseek.com/quick_start/pricing"

def fetch_latest():
    """用内置 http.client 抓取定价页面"""
    import http.client, ssl
    conn = http.client.HTTPSConnection("api-docs.deepseek.com", context=ssl._create_unverified_context())
    conn.request("GET", "/quick_start/pricing")
    resp = conn.getresponse()
    html = resp.read().decode("utf-8")
    conn.close()

    prices = {}

    # 正则匹配 V4-Flash 价格
    # 页面结构: V4-Flash | $0.0028 | $0.14 | $0.28
    flash_match = re.search(r'deepseek-v4-flash.*?\$([\d.]+).*?\$([\d.]+).*?\$([\d.]+)', html, re.DOTALL)
    if flash_match:
        prices["DeepSeek-V4-Flash"] = {
            "input": round(float(flash_match.group(2)), 2),
            "output": round(float(flash_match.group(3)), 2),
            "cache_read": round(float(flash_match.group(1)), 2),
            "cache_create": round(float(flash_match.group(3)), 2)
        }

    # 正则匹配 V4-Pro 价格（75% off 折扣价）
    # $0.003625 (75% off)$0.0145 | $0.435 (75% off)$1.74 | $0.87 (75% off)$3.48
    pro_match = re.findall(r'\$([\d.]+)\s*\(75% off\)\s*<del>\$[\d.]+</del>', html)
    if len(pro_match) >= 3:
        prices["DeepSeek-V4-Pro"] = {
            "input": round(float(pro_match[1]), 2),
            "output": round(float(pro_match[2]), 2),
            "cache_read": round(float(pro_match[0]), 2),
            "cache_create": round(float(pro_match[2]), 2)
        }
    else:
        # fallback: try regex without the <del> tag
        pro_match2 = re.findall(r'\$([\d.]+)\s*\(75% off\)\$([\d.]+)', html)
        if len(pro_match2) >= 3:
            prices["DeepSeek-V4-Pro"] = {
                "input": round(float(pro_match2[1].split(')')[0]), 2) if ')' in pro_match2[1] else round(float(pro_match2[1]), 2),
                "output": round(float(pro_match2[2].split(')')[0]), 2) if ')' in pro_match2[2] else round(float(pro_match2[2]), 2),
                "cache_read": round(float(pro_match2[0].split(')')[0]), 2) if ')' in pro_match2[0] else round(float(pro_match2[0]), 2),
                "cache_create": round(float(pro_match2[2].split(')')[0]), 2) if ')' in pro_match2[2] else round(float(pro_match2[2]), 2)
            }

    # V3.2 - 从搜索结果中确认的价格
    prices["DeepSeek-V3.2"] = {"input": 2.0, "output": 3.0, "cache_read": 0.2, "cache_create": 3.0}

    # 转换成人民币（汇率 7.2）
    for model in list(prices.keys()):
        p = prices[model]
        prices[model] = {
            "input": round(p["input"] * 7.2, 2),
            "output": round(p["output"] * 7.2, 2),
            "cache_read": round(p["cache_read"] * 7.2, 2),
            "cache_create": round(p["cache_create"] * 7.2, 2)
        }

    prices["_updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    prices["_source"] = PRICING_URL
    return prices

def main():
    if "--dry-run" in sys.argv:
        prices = fetch_latest()
        print(json.dumps(prices, indent=2, ensure_ascii=False))
        return

    print(f"从 {PRICING_URL} 抓取最新价格...")
    try:
        prices = fetch_latest()
    except Exception as e:
        print(f"抓取失败: {e}")
        print("请手动访问 https://api-docs.deepseek.com/quick_start/pricing 更新 pricing.json")
        sys.exit(1)

    # 备份旧文件
    if os.path.exists(PRICING_FILE):
        backup = PRICING_FILE + ".bak"
        with open(PRICING_FILE, "r") as f:
            old = json.load(f)
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(old, f, indent=2, ensure_ascii=False)
        print(f"已备份旧价格到 {backup}")

    with open(PRICING_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=2, ensure_ascii=False)

    print(f"定价已更新: {PRICING_FILE}")
    for k, v in prices.items():
        if k.startswith("_"): continue
        print(f"  {k}: ¥{v['input']}/¥{v['output']} /1M tokens")
    print(f"\n更新时间: {prices['_updated_at']}")
    print("\n重启 token dashboard 即可看到更新后的花费。")

if __name__ == "__main__":
    main()
