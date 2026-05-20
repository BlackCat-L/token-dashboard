#!/usr/bin/env python3
"""分析层：省钱建议 + 数据聚合"""
from collections import defaultdict
from datetime import datetime


class TipsEngine:
    """省钱建议生成器，4 类规则"""

    @staticmethod
    def generate(all_sessions: list) -> list:
        tips = []
        now = datetime.now()

        # 1. 缓存纪律 — 7天内缓存命中率 < 40%
        recent = [s for s in all_sessions
                  if s.first_ts and (now - datetime.fromisoformat(s.first_ts)).days <= 7]
        if recent:
            total_cr = sum(s.cache_read for s in recent)
            total_cc = sum(s.cache_create for s in recent)
            hit_rate = total_cr / max(total_cr + total_cc, 1) * 100
            if hit_rate < 40:
                tips.append({"id": "cache-discipline", "level": "warn",
                    "title": f"缓存命中率仅 {hit_rate:.1f}%", "saving": "¥0.1-2/会话",
                    "detail": "频繁重复加载上下文。建议缩小 Skill 文件、减少 CLAUDE.md 行数。"})

        # 2. 重复读文件 — 同一文件被任何工具操作超过10次
        from collections import Counter
        file_counter = Counter()
        for s in all_sessions:
            for td in s.tools.values():
                for fname, fc in td["files"].items():
                    file_counter[fname] += fc
        repeat_files = [(f, c) for f, c in file_counter.most_common(5) if c > 10]
        for fname, count in repeat_files[:2]:
            tips.append({"id": f"repeat-file-{fname}", "level": "info",
                "title": f"文件 {fname} 被操作 {count} 次", "saving": "减少上下文加载",
                "detail": f"考虑将 {fname} 的核心内容加入 CLAUDE.md 或 Skill，减少每次重新读取。"})

        # 3. 模型降级 — 短回复
        expensive_models = {"DeepSeek-V3.2"}
        short_count = sum(1 for s in all_sessions
                          for m, c in s.model_msgs.items()
                          if any(em in m for em in expensive_models) and s.output < 500)
        if short_count > 3:
            tips.append({"id": "model-downgrade", "level": "info",
                "title": f"{short_count} 次高价模型短回复(<500 token)", "saving": "可达 50-80% 成本",
                "detail": "短回复任务可以切换到更便宜的模型。"})

        # 4. 结果过大
        big_tools = []
        for s in all_sessions:
            for tn, td in s.tools.items():
                if td["tokens"] > 50000:
                    big_tools.append((tn, round(td["tokens"])))
        if big_tools:
            biggest = sorted(big_tools, key=lambda x: -x[1])[0]
            tips.append({"id": "large-results", "level": "info",
                "title": f"工具 {biggest[0]} 返回结果过大", "saving": "减少上下文浪费",
                "detail": f"单次返回 {biggest[1]:,} token，建议限制输出范围或分页获取。"})
        return tips


class Aggregator:
    """多维度数据聚合"""

    @staticmethod
    def by_task(all_sessions: list) -> dict:
        d = defaultdict(lambda: {"sessions": 0, "total": 0, "actual": 0})
        for s in all_sessions:
            d[s.task]["sessions"] += 1
            d[s.task]["total"] += s.total
            d[s.task]["actual"] += s.input + s.output
        return dict(d)

    @staticmethod
    def by_tool(all_sessions: list) -> dict:
        d = defaultdict(lambda: {"count": 0, "tokens": 0, "files": defaultdict(int)})
        for s in all_sessions:
            for tn, td in s.tools.items():
                d[tn]["count"] += td["count"]
                d[tn]["tokens"] += td["tokens"]
                for fn, fc in td["files"].items():
                    d[tn]["files"][fn] += fc
        return dict(d)

    @staticmethod
    def by_skill(all_sessions: list) -> dict:
        d = defaultdict(lambda: {"total_size": 0, "sessions": 0, "first_sessions": 0})
        for s in all_sessions:
            for sn, sd in s.skills.items():
                d[sn]["total_size"] += sd["size"]
                d[sn]["sessions"] += 1
                if sd["first_seen"]: d[sn]["first_sessions"] += 1
        return dict(d)

    @staticmethod
    def by_date(all_sessions: list) -> dict:
        d = defaultdict(lambda: {"input": 0, "output": 0, "total": 0, "count": 0})
        for s in all_sessions:
            day = s.first_ts[:10] if s.first_ts else "???"
            d[day]["input"] += s.input
            d[day]["output"] += s.output
            d[day]["total"] += s.total
            d[day]["count"] += 1
        return dict(d)

    @staticmethod
    def by_subagent(all_sessions: list) -> dict:
        d = defaultdict(lambda: {"count": 0, "tokens": 0, "desc": ""})
        for s in all_sessions:
            for sn, sd in s.subagents.items():
                d[sn]["count"] += sd["count"]
                d[sn]["tokens"] += sd["tokens"]
                if sd.get("desc") and not d[sn]["desc"]:
                    d[sn]["desc"] = sd["desc"]
        return dict(d)

    @staticmethod
    def by_model(all_sessions: list) -> dict:
        d = defaultdict(int)
        for s in all_sessions:
            for m, c in s.model_msgs.items():
                d[m] += c
        return dict(d)

    @staticmethod
    def by_hour(all_sessions: list) -> list:
        return [sum(s.hours[h] for s in all_sessions) for h in range(24)]

    @staticmethod
    def mcp_tax(all_sessions: list) -> tuple:
        """统计 MCP 上下文税"""
        KNOWN_TOOLS = {"gladekit-unity": 80, "playwright": 30, "dotnet-analyzer": 10,
                       "claude-notifier": 2, "cloudflare-image": 6, "pollinations": 5}
        server_tools = defaultdict(set)
        for s in all_sessions:
            for tn in s.tools:
                if tn.startswith("mcp__"):
                    parts = tn.split("__", 1)
                    if len(parts) == 2:
                        sname = parts[1].split("__")[0]
                        tname = parts[1].split("__", 1)[1] if "__" in parts[1] else parts[1]
                        server_tools[sname].add(tname)

        total_msgs = sum(sum(s.model_msgs.values()) for s in all_sessions)
        TOK_PER_TOOL = 200
        results = []
        for sname in sorted(server_tools):
            unique = len(server_tools[sname])
            if not unique: continue
            per_turn = unique * TOK_PER_TOOL
            results.append({
                "name": sname, "tools": unique, "per_turn": per_turn,
                "total_overhead": per_turn * total_msgs,
                "sample_tools": sorted(list(server_tools[sname]))[:5],
            })
        return results, total_msgs
