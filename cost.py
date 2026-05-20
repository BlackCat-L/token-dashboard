#!/usr/bin/env python3
"""计费层：模型定价 + 会话花费计算"""
import json as _json, os


class Pricing:
    """模型定价表，支持大小写不敏感匹配 + Claude→DeepSeek 映射"""

    def __init__(self, pricing_path: str = None):
        if pricing_path is None:
            pricing_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pricing.json")
        self._path = pricing_path
        self._data = {}
        self.updated_at = ""
        self.source = ""
        self.reload()

    def reload(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = _json.load(f)
            self.updated_at = self._data.pop("_updated_at", "?")
            self.source = self._data.pop("_source", "")
        except:
            self._data = {}

    def get(self, model_name: str) -> dict:
        """按模型名获取定价，支持大小写不敏感和 Claude 映射"""
        mkey = model_name.split("@")[0].lower().replace("-", "").replace("_", "").replace(".", "")
        for pk in self._data:
            if pk.lower().replace("-", "").replace("_", "").replace(".", "") == mkey:
                return self._data[pk]
        return {}

    def __iter__(self):
        return iter(self._data)


class CostCalculator:
    """按 DeepSeek 3 项计费公式：输入(缓存未命中) + 输出 + 输入(缓存命中)"""

    def __init__(self, pricing: Pricing):
        self.pricing = pricing

    def calc(self, session) -> float:
        """计算单会话花费（¥），返回 (cost, top_model)"""
        msgs = getattr(session, "model_msgs", {})
        if not msgs:
            return 0.0, ""
        total_msgs = sum(msgs.values())

        w_input = w_output = w_cr = 0.0
        best_price = None
        for model, count in msgs.items():
            p = self.pricing.get(model)
            if not p: continue
            ratio = count / total_msgs
            w_input += p.get("input", 0) * ratio
            w_output += p.get("output", 0) * ratio
            w_cr += p.get("cache_read", 0) * ratio
            if best_price is None or p.get("input", 0) < best_price.get("input", 9):
                best_price = p

        # input 已含 cache_read，需减去后按缓存未命中价计
        new_input = max(session.input - session.cache_read, 0)
        cost = (new_input / 1e6 * w_input +
                session.output / 1e6 * w_output +
                session.cache_read / 1e6 * w_cr)
        top_model = max(msgs, key=msgs.get) if msgs else ""
        return round(cost, 4), top_model

    def cost_callback(self, session):
        """供 SessionStore 回调使用"""
        return self.calc(session)
