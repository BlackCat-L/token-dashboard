#!/usr/bin/env python3
"""Session 数据层：JSONL 解析、消息去重、SQLite 缓存"""
import json as _json, os, glob, sqlite3
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.expanduser("~/.claude/projects")
CACHE_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_cache.db")

# ── 工具函数 ──

def project_name(dirname: str) -> str:
    parts = dirname.split("--")
    return parts[-1] if len(parts) > 1 else dirname

def classify_task(first_msg: str, slug: str) -> str:
    msg = (first_msg + " " + slug).lower()
    rules = [
        (["推送","push","oppo","vivo","xiaomi","小米","华为","huawei","荣耀","honor","meizu","魅族",
          "厂商","token注册","agconnect","notification","来电","call activity","pushservice","pushreceiver"],"Push SDK 集成"),
        (["报错","崩溃","crash","bug","修复","null","exception","error","失败","修了","修好",
          "fix","问题","不对","错误","ioexception","nullreference","sharing violation"],"Bug 修复"),
        (["ui","面板","界面","按钮","canvas","界面","弹窗","对话框","dialog","panel",
          "showconfirm","inputfield","scroll","布局","layout"],"UI 开发"),
        (["gradle","aab","apk","打包","构建","build","plugin","library","manifest","maven","依赖","android studio"],"构建/打包"),
        (["live2d","捏脸","面部","表情","face","sculpt","cubism","模型"],"捏脸/Live2D"),
        (["聊天","对话","chat","sse","消息","conversation","message","回复"],"聊天系统"),
        (["bridge","unitybridge","tcp","端口","port","8765","通信","连接"],"Unity Bridge"),
        (["飞书","lark","feishu","日历","文档","表格","多维","base","im","消息"],"飞书集成"),
        (["token","用量","面板","dashboard","分析","统计","noctrace","skill","mcp","配置","config","setting","工具链","hook","权限"],"工具/配置"),
        (["架构","architecture","gamearchitec","重构","系统","system","设计","model","utility","框架","qframework"],"架构设计"),
        (["网络","http","api","baseurl","服务器","请求","url","ssl","证书","network","security","proxy"],"网络/API"),
        (["场景","unity","gameobject","脚本","component","shader","特效","动画","animator","prefab","资源","asset"],"Unity 开发"),
    ]
    for keywords, label in rules:
        if any(k in msg for k in keywords): return label
    return "其他"


# ── SessionData ──

class SessionData:
    """单个会话的数据容器"""
    __slots__ = ("id","file","project","input","output","cache_create","cache_read",
                 "first_ts","last_ts","first_msg","slug","task","total","cost","top_model",
                 "tools","model_msgs","skills","subagents","hours","timeline")

    def __init__(self, sid: str, fname: str):
        self.id = sid; self.file = fname
        self.input = 0; self.output = 0
        self.cache_create = 0; self.cache_read = 0
        self.project = ""  # 所属项目名，由外部赋值
        self.first_ts = None; self.last_ts = None
        self.first_msg = ""; self.slug = ""
        self.task = ""; self.total = 0; self.cost = 0.0; self.top_model = ""
        self.tools = defaultdict(lambda: {"count": 0, "tokens": 0, "files": defaultdict(int)})
        self.model_msgs = defaultdict(int)
        self.skills = defaultdict(lambda: {"size": 0, "first_seen": False})
        self.subagents = defaultdict(lambda: {"count": 0, "tokens": 0, "desc": ""})
        self.hours = [0] * 24
        self.timeline = []

    def to_dict(self) -> dict:
        return {
            "id": self.id, "file": self.file,
            "input": self.input, "output": self.output,
            "cache_create": self.cache_create, "cache_read": self.cache_read,
            "first_ts": self.first_ts, "last_ts": self.last_ts,
            "first_msg": self.first_msg, "slug": self.slug,
            "task": self.task, "total": self.total,
            "cost": self.cost, "top_model": self.top_model,
            "tools": {k: {"count": v["count"], "tokens": v["tokens"], "files": dict(v["files"])}
                      for k, v in self.tools.items()},
            "model_msgs": dict(self.model_msgs),
            "skills": {k: {"size": v["size"], "first_seen": v["first_seen"]} for k, v in self.skills.items()},
            "subagents": dict(self.subagents),
            "hours": self.hours, "timeline": self.timeline,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionData":
        s = cls(d["id"], d["file"])
        for k in ("input","output","cache_create","cache_read","first_ts","last_ts",
                  "first_msg","slug","task","total","cost","top_model"):
            setattr(s, k, d.get(k, 0 if k in ("cost","total") else ""))
        s.tools = defaultdict(lambda: {"count": 0, "tokens": 0, "files": defaultdict(int)},
            {k: {"count": v["count"], "tokens": v["tokens"], "files": defaultdict(int, v["files"])}
             for k, v in d.get("tools", {}).items()})
        s.model_msgs = defaultdict(int, d.get("model_msgs", {}))
        s.skills = defaultdict(lambda: {"size": 0, "first_seen": False}, d.get("skills", {}))
        s.subagents = defaultdict(lambda: {"count": 0, "tokens": 0, "desc": ""}, d.get("subagents", {}))
        s.hours = d.get("hours", [0]*24)
        s.timeline = d.get("timeline", [])
        return s

    def serialize(self) -> str:
        return _json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def deserialize(cls, jstr: str) -> "SessionData":
        return cls.from_dict(_json.loads(jstr))


# ── SessionStore ──

class SessionStore:
    """管理所有项目的会话数据，含 SQLite 缓存"""

    def __init__(self, pricing_callback=None):
        self._pricing_cb = pricing_callback  # fn(session, pricing) -> (cost, top_model)

    def load_project(self, proj_dir: str) -> list:
        """解析一个项目目录下所有 .jsonl 文件，返回 SessionData 列表"""
        conn = sqlite3.connect(CACHE_DB)
        conn.execute("CREATE TABLE IF NOT EXISTS cache (file_path TEXT PRIMARY KEY, mtime REAL, session_json TEXT)")
        cache_hits = 0
        sessions = []

        for f in sorted(glob.glob(os.path.join(proj_dir, "*.jsonl"))):
            fpath = os.path.abspath(f); mtime = os.path.getmtime(fpath)
            row = conn.execute("SELECT mtime, session_json FROM cache WHERE file_path=?",
                               (fpath,)).fetchone()
            if row and row[0] == mtime:
                sessions.append(SessionData.deserialize(row[1]))
                cache_hits += 1
                continue

            s = SessionData(os.path.splitext(os.path.basename(f))[0],
                           os.path.basename(f))
            self._parse_jsonl(f, s)
            s.task = classify_task(s.first_msg, s.slug)
            s.total = s.input + s.output + s.cache_create + s.cache_read

            if s.first_ts:
                if self._pricing_cb:
                    s.cost, s.top_model = self._pricing_cb(s)
                sessions.append(s)
                try:
                    conn.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)",
                                 (fpath, mtime, s.serialize()))
                except: pass

        conn.commit(); conn.close()
        if cache_hits:
            print(f"  (缓存命中 {cache_hits}/{len(sessions)} 会话)")
        return sessions

    def scan_all(self) -> list:
        """扫描所有项目"""
        projects = []
        for d in sorted(glob.glob(os.path.join(BASE_DIR, "*"))):
            if not os.path.isdir(d): continue
            if not glob.glob(os.path.join(d, "*.jsonl")): continue
            name = project_name(os.path.basename(d))
            sessions = self.load_project(d)
            total = sum(s.input + s.output + s.cache_create + s.cache_read for s in sessions)
            projects.append({"dir": os.path.basename(d), "name": name,
                           "sessions": len(sessions), "total": total, "data": sessions})
        return projects

    def _parse_jsonl(self, filepath: str, s: SessionData):
        """解析单个 JSONL 文件到 SessionData"""
        with open(filepath, "r", encoding="utf-8") as fh:
            got_first_msg = False
            pending_msgs = {}

            for line in fh:
                if not line.strip(): continue
                try: obj = _json.loads(line)
                except: continue

                t = obj.get("type"); ts_str = obj.get("timestamp", "")
                hour = None
                if ts_str:
                    try: hour = datetime.fromisoformat(ts_str.replace("Z","+00:00")).hour
                    except: pass
                    iso = ts_str[:19]
                    if s.first_ts is None or iso < s.first_ts: s.first_ts = iso
                    if s.last_ts is None or iso > s.last_ts: s.last_ts = iso

                slug = obj.get("slug", "")
                if slug and not s.slug: s.slug = slug

                if t == "user" and not got_first_msg:
                    for block in obj.get("message", {}).get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            txt = block.get("text", "")
                            if len(txt) > 15:
                                s.first_msg = txt; got_first_msg = True; break

                if t == "attachment" and obj.get("attachment", {}).get("type") == "skill_listing":
                    content = obj.get("attachment", {}).get("content", "")
                    is_init = obj.get("attachment", {}).get("isInitial", False)
                    for li in content.split("\n"):
                        li = li.strip()
                        if li.startswith("- "):
                            sn = li[2:].split(":")[0].strip()
                            if sn: s.skills[sn]["size"] += len(li)
                            if is_init: s.skills[sn]["first_seen"] = True

                if t == "assistant":
                    msg = obj.get("message", {}); usage = msg.get("usage", {})
                    msg_id = msg.get("id")
                    if msg_id and usage.get("input_tokens", 0) + usage.get("output_tokens", 0) > 0:
                        pending_msgs[msg_id] = {"hour": hour, "model": msg.get("model", "?"),
                                                "usage": usage, "content": msg.get("content", [])}

            # 去重后累加
            tc = 0
            for msg_id, pm in pending_msgs.items():
                hour = pm["hour"]
                if hour is not None: s.hours[hour] += 1
                s.model_msgs[pm["model"]] += 1
                usage = pm["usage"]
                s.input += usage.get("input_tokens", 0)
                out = usage.get("output_tokens", 0); s.output += out
                s.cache_create += usage.get("cache_creation_input_tokens", 0)
                s.cache_read += usage.get("cache_read_input_tokens", 0)

                content = pm["content"]
                tool_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                if tool_blocks and out > 0:
                    tpt = out / len(tool_blocks)
                    for blk in tool_blocks:
                        tn = blk.get("name", "?")
                        s.tools[tn]["count"] += 1
                        s.tools[tn]["tokens"] += tpt
                        inp = blk.get("input", {})
                        fp = inp.get("file_path") or inp.get("path") or inp.get("scriptPath") or inp.get("prefabPath") or ""
                        if fp: s.tools[tn]["files"][os.path.basename(fp)] += 1
                        # Subagent 归因
                        if tn == "Agent":
                            st = inp.get("subagent_type", "")
                            desc = inp.get("description", "")[:50]
                            if not st and desc:
                                dlow = desc.lower()
                                if "explore" in dlow: st = "Explore"
                                elif "plan" in dlow: st = "Plan"
                                elif "general" in dlow: st = "general-purpose"
                                else: st = "general-purpose"
                            if st:
                                s.subagents[st]["count"] += 1
                                s.subagents[st]["tokens"] += tpt
                                if desc and not s.subagents[st].get("desc"):
                                    s.subagents[st]["desc"] = desc
                if tc < 200:
                    for blk in tool_blocks:
                        if tc >= 200: break
                        inp = blk.get("input", {})
                        fp = inp.get("file_path") or inp.get("path") or inp.get("scriptPath") or inp.get("prefabPath") or ""
                        s.timeline.append({"h": hour or 0, "tool": blk.get("name","?"),
                                          "file": os.path.basename(fp) if fp else "",
                                          "tok": round(tpt if tool_blocks else 0)})
                        tc += 1
