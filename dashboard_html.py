#!/usr/bin/env python3
"""HTML 生成层"""
import json as _json
from collections import defaultdict
from analytics import Aggregator
from cost import Pricing, CostCalculator


class HTMLBuilder:
    """生成完整的 Token Dashboard HTML 页面"""

    def __init__(self, pricing: Pricing):
        self.pricing = pricing

    def build(self, projects: list) -> str:
        pricing = self.pricing
        all_sessions = []
        for p in projects:
            for s in p["data"]:
                s.project = p["name"]
                all_sessions.append(s)

        total_input = sum(s.input for s in all_sessions)
        total_output = sum(s.output for s in all_sessions)
        total_cache_create = sum(s.cache_create for s in all_sessions)
        total_cache_read = sum(s.cache_read for s in all_sessions)
        actual = total_input + total_output
        total_cost = sum(s.cost for s in all_sessions)

        proj_opts = "\n".join(
            f'<option value="{p["name"]}">{p["name"]} · {p["sessions"]}会话 · {(p["total"]/1e6):.1f}M tokens</option>'
            for p in projects)

        global_msgs = defaultdict(int)
        for s in all_sessions:
            for m, c in s.model_msgs.items(): global_msgs[m] += c
        top_model = max(global_msgs, key=global_msgs.get) if global_msgs else "?"
        top_model = top_model.split("@")[0]
        top_model = top_model.replace("deepseek","DeepSeek").replace("claude","Claude").replace("v4","V4").replace("v3","V3").replace("-pro","-Pro").replace("-flash","-Flash").replace("opus","Opus").replace("sonnet","Sonnet").replace("haiku","Haiku")

        from analytics import TipsEngine
        tips = TipsEngine.generate(all_sessions)
        mcp_tax, total_asst_msgs = Aggregator.mcp_tax(all_sessions)

        cache_hit = total_cache_read / max(total_cache_create + total_cache_read, 1) * 100
        cache_save = total_cache_read / max(total_input + total_cache_create + total_cache_read, 1) * 100

        proj_data = {}
        for p in projects:
            sl = p["data"]
            proj_data[p["name"]] = {
                "sessions": [self._session_dict(s) for s in sl],
                "tasks": Aggregator.by_task(sl),
                "tools": Aggregator.by_tool(sl),
                "skills": Aggregator.by_skill(sl),
                "daily": Aggregator.by_date(sl),
                "total": sum(s.total for s in sl),
                "actual": sum(s.input + s.output for s in sl),
                "input": sum(s.input for s in sl),
                "output": sum(s.output for s in sl),
                "cache_read": sum(s.cache_read for s in sl),
                "cache_create": sum(s.cache_create for s in sl),
                "count": len(sl),
                "hours": Aggregator.by_hour(sl),
                "total_cost": sum(s.cost for s in sl),
                "subagents": Aggregator.by_subagent(sl),
                "model_msgs": Aggregator.by_model(sl),
            }
        proj_data["_全部项目"] = {
            "tasks": Aggregator.by_task(all_sessions),
            "tools": Aggregator.by_tool(all_sessions),
            "skills": Aggregator.by_skill(all_sessions),
            "daily": Aggregator.by_date(all_sessions),
            "hours": Aggregator.by_hour(all_sessions),
            "total_cost": total_cost,
            "total": sum(s.total for s in all_sessions),
            "actual": actual,
            "input": total_input, "output": total_output,
            "cache_read": total_cache_read, "cache_create": total_cache_create,
            "count": len(all_sessions),
            "subagents": Aggregator.by_subagent(all_sessions),
            "model_msgs": Aggregator.by_model(all_sessions),
        }

        tips_json = _json.dumps(tips, ensure_ascii=False)
        pricing_json = _json.dumps({k: v for k, v in pricing._data.items() if not k.startswith("_")}, ensure_ascii=False)
        mcp_tax_json = _json.dumps(mcp_tax, ensure_ascii=False)
        proj_json = _json.dumps(proj_data, ensure_ascii=False)

        return self._html_template(proj_opts, actual, total_cache_read, total_cache_create,
                                    cache_hit, cache_save, len(all_sessions), total_cost,
                                    top_model, pricing, proj_json, tips_json, pricing_json,
                                    mcp_tax_json, total_asst_msgs)

    def _session_dict(self, s) -> dict:
        return {
            "id": s.id[:8], "task": s.task,
            "date": s.first_ts[:10] if s.first_ts else "?",
            "ts": s.first_ts or "",
            "input": s.input, "output": s.output,
            "total": s.total, "cache_read": s.cache_read, "cache_create": s.cache_create,
            "cost": getattr(s, "cost", 0),
            "first_msg": s.first_msg[:120],
            "hours": s.hours, "timeline": s.timeline[:200],
            "tools": {k: {"count": v["count"], "tokens": v["tokens"], "files": dict(v["files"])}
                      for k, v in dict(s.tools).items()},
            "skills": list(s.skills.keys()),
            "subagents": dict(s.subagents),
            "model_msgs": dict(s.model_msgs),
        }

    def _html_template(self, proj_opts, actual, total_cache_read, total_cache_create,
                       cache_hit, cache_save, session_count, total_cost, top_model,
                       pricing, proj_json, tips_json, pricing_json, mcp_tax_json, total_asst_msgs) -> str:
        p_updated = pricing.updated_at
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Claude Code Token 用量面板 v6</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei','PingFang SC',sans-serif; background:#0f1419; color:#e7e9ea; }}
.header {{ background:#1d2329; padding:12px 24px; border-bottom:1px solid #2f353c; display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
.header h1 {{ font-size:19px; color:#fff; }}
.header select {{ background:#1d2329; color:#fff; border:1px solid #2f353c; padding:6px 12px; border-radius:6px; font-size:13px; outline:none; cursor:pointer; }}
.header select:focus {{ border-color:#1d9bf0; }}
.header .btn {{ background:#1d2f3f; color:#1d9bf0; border:1px solid #2f353c; padding:6px 14px; border-radius:6px; font-size:12px; cursor:pointer; }}
.header .btn:hover {{ background:#2a4055; }}
.search-bar {{ padding:10px 24px; display:flex; gap:10px; align-items:center; }}
.search-bar input {{ flex:1; background:#1d2329; border:1px solid #2f353c; color:#fff; padding:7px 14px; border-radius:6px; font-size:13px; outline:none; max-width:420px; }}
.search-bar input:focus {{ border-color:#1d9bf0; }}
.search-bar .hint {{ font-size:11px; color:#8b98a5; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; padding:14px 24px; }}
.card {{ background:#1d2329; border:1px solid #2f353c; border-radius:8px; padding:14px; }}
.card .label {{ font-size:11px; color:#8b98a5; margin-bottom:2px; }}
.card .value {{ font-size:24px; font-weight:700; }}
.card.green .value {{ color:#00ba7c; }}
.card.blue .value {{ color:#1d9bf0; }}
.card.yellow .value {{ color:#ffad1f; }}
.card.purple .value {{ color:#8b5cf6; }}
.tabs {{ display:flex; gap:0; padding:0 24px; border-bottom:1px solid #2f353c; overflow-x:auto; }}
.tab {{ padding:9px 16px; cursor:pointer; font-size:13px; color:#8b98a5; border-bottom:2px solid transparent; transition:.2s; white-space:nowrap; }}
.tab:hover,.tab.active {{ color:#fff; border-bottom-color:#1d9bf0; }}
.content {{ padding:16px 24px; }}
.section {{ display:none; }}
.section.active {{ display:block; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
tr:nth-child(even) td {{ background:#141a20; }}
tr:hover td {{ background:#1a2530 !important; }}
th {{ text-align:center; padding:9px 10px; border-bottom:2px solid #2f353c; color:#8b98a5; font-weight:600; font-size:11px; white-space:nowrap; }}
th:first-child {{ text-align:left; padding-left:16px; }}
td {{ padding:8px 12px; border-bottom:1px solid #1d2329; vertical-align:middle; }}
td:first-child {{ text-align:center; color:#8b98a5; font-size:11px; width:36px; }}
.num {{ text-align:center; font-variant-numeric:tabular-nums; font-family:'Cascadia Code','Consolas',monospace; }}
.tag {{ display:inline-block; background:#1d2f3f; color:#1d9bf0; padding:1px 7px; border-radius:3px; font-size:10px; margin:1px; }}
.file-list {{ font-size:10px; color:#8b98a5; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:left; }}
.chart-container {{ margin:16px 0; }}
.bar-row {{ display:flex; align-items:center; margin:5px 0; gap:8px; }}
.bar-label {{ width:90px; text-align:right; font-size:11px; color:#8b98a5; flex-shrink:0; }}
.bar-fill {{ height:20px; border-radius:3px; display:flex; align-items:center; padding-left:8px; font-size:10px; font-weight:600; min-width:26px; }}
.bar-value {{ font-size:11px; color:#e7e9ea; flex-shrink:0; }}
.bar-pct {{ font-size:10px; color:#8b98a5; flex-shrink:0; }}
code {{ background:#1d2f3f; padding:1px 5px; border-radius:2px; font-size:11px; }}
.info-box {{ background:#1a2520; border:1px solid #2a4a30; border-radius:6px; padding:12px 16px; margin-bottom:16px; font-size:12px; color:#8b98a5; }}
.info-box strong {{ color:#00ba7c; }}
.heatmap {{ display:grid; grid-template-columns:60px repeat(24,1fr); gap:3px; font-size:10px; margin:16px 0; }}
.heatmap .hlabel {{ color:#8b98a5; text-align:right; padding-right:8px; line-height:20px; }}
.heatmap .hcell {{ width:100%; aspect-ratio:1; border-radius:2px; background:#1d2329; cursor:pointer; transition:.15s; }}
.heatmap .hcell:hover {{ outline:2px solid #fff; z-index:1; }}
.heatmap .hheader {{ text-align:center; color:#8b98a5; font-size:9px; padding-top:4px; }}
.modal-overlay {{ display:none; position:fixed; top:0;left:0;right:0;bottom:0; background:rgba(0,0,0,0.7); z-index:100; justify-content:center; align-items:center; }}
.modal-overlay.show {{ display:flex; }}
.modal {{ background:#1d2329; border:1px solid #2f353c; border-radius:12px; padding:24px; max-width:800px; max-height:85vh; overflow-y:auto; width:90%; }}
.modal h2 {{ font-size:18px; margin-bottom:4px; }}
.modal .sub {{ font-size:12px; color:#8b98a5; margin-bottom:16px; }}
.modal .close {{ float:right; background:none; border:none; color:#8b98a5; font-size:24px; cursor:pointer; }}
.modal .close:hover {{ color:#fff; }}
.timeline-row {{ display:flex; align-items:center; padding:4px 0; gap:8px; font-size:11px; border-bottom:1px solid #1d2329; }}
.timeline-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
.timeline-hour {{ color:#8b98a5; width:30px; flex-shrink:0; }}
.timeline-tool {{ font-weight:600; width:120px; flex-shrink:0; }}
.timeline-file {{ flex:1; color:#8b98a5; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.timeline-tok {{ color:#ffad1f; flex-shrink:0; }}
.highlight {{ background:#3a3510; border-radius:2px; padding:0 2px; }}
.group-header {{ background:#1a2530; padding:10px 16px; margin:16px 0 0 0; border-left:3px solid #1d9bf0; font-size:13px; font-weight:600; display:flex; justify-content:space-between; align-items:center; }}
.group-header .group-name {{ color:#fff; }}
.group-header .group-stats {{ font-size:11px; color:#8b98a5; font-weight:400; }}
</style>
</head>
<body>
<div class="header">
    <h1>Token 用量面板 v6</h1>
    <select id="projSelect" onchange="switchProject(this.value)"><option value="_全部项目">全部项目 · {session_count}会话 · {actual/1e6:.1f}M tokens</option>{proj_opts}</select>
    <button class="btn" onclick="exportCSV()">导出 CSV</button>
</div>
<div id="tips-bar" style="padding:0 24px;"></div>
<div class="search-bar">
    <input id="searchInput" type="text" placeholder="搜索会话、工具、文件、Skill..." oninput="onSearch()">
    <span class="hint" id="searchHint"></span>
</div>
<div class="cards" id="cards">
    <div class="card green"><div class="label">实际消耗 (Input+Output)</div><div class="value" id="val-actual">{actual:,.0f}</div></div>
    <div class="card blue"><div class="label">缓存读取</div><div class="value" id="val-cacheR">{total_cache_read:,.0f}</div></div>
    <div class="card yellow"><div class="label">缓存命中率</div><div class="value" id="val-hitrate">{cache_hit:.1f}%</div></div>
    <div class="card purple"><div class="label">节省比例</div><div class="value" id="val-saverate">{cache_save:.1f}%</div></div>
    <div class="card"><div class="label">会话总数</div><div class="value" style="color:#e7e9ea;" id="val-count">{session_count}</div></div>
    <div class="card"><div class="label">缓存创建</div><div class="value" style="color:#e7e9ea;" id="val-cacheC">{total_cache_create:,.0f}</div></div>
    <div class="card green"><div class="label">{top_model} 预估花费</div><div class="value" id="val-cost">¥{total_cost:.2f}</div><div class="label" style="font-size:10px;margin-top:4px;">价格 {p_updated}</div></div>
</div>
<div class="tabs">
    <div class="tab active" onclick="switchTab('sessions')">会话排行</div>
    <div class="tab" onclick="switchTab('tasks')">任务类型</div>
    <div class="tab" onclick="switchTab('tools')">工具消耗</div>
    <div class="tab" onclick="switchTab('skills')">Skill 成本</div>
    <div class="tab" onclick="switchTab('daily')">每日趋势</div>
    <div class="tab" onclick="switchTab('heatmap')">活动热力图</div>
    <div class="tab" onclick="switchTab('subagents')">代理归因</div>
    <div class="tab" onclick="switchTab('models')">模型花费</div>
    <div class="tab" onclick="switchTab('mcptax')">MCP 税</div>
</div>
<div class="content">
    <div id="tab-sessions" class="section active">
        <h3 style="margin-bottom:12px;">会话排行 <span style="font-size:11px;color:#8b98a5;" id="sess-count"></span></h3>
        <div style="display:flex;gap:12px;margin-bottom:12px;align-items:center;">
            <label style="font-size:12px;color:#8b98a5;">分组：</label>
            <select id="groupBy" onchange="renderSessions()" style="background:#1d2329;color:#fff;border:1px solid #2f353c;padding:4px 8px;border-radius:4px;font-size:12px;">
                <option value="none">无分组</option><option value="date">按日期</option><option value="task">按任务类型</option></select>
            <label style="font-size:12px;color:#8b98a5;">排序：</label>
            <select id="sortBy" onchange="renderSessions()" style="background:#1d2329;color:#fff;border:1px solid #2f353c;padding:4px 8px;border-radius:4px;font-size:12px;">
                <option value="total">总Token降序</option><option value="time">时间降序</option><option value="count">会话数降序</option></select>
            <label style="font-size:12px;color:#8b98a5;">显示：</label>
            <select id="limitBy" onchange="renderSessions()" style="background:#1d2329;color:#fff;border:1px solid #2f353c;padding:4px 8px;border-radius:4px;font-size:12px;">
                <option value="30">前30条</option><option value="50">前50条</option><option value="100">前100条</option><option value="999">全部</option></select>
        </div>
        <table><thead><tr><th>#</th><th>日期</th><th>项目</th><th>任务</th><th>花费</th><th>实际消耗</th><th>缓存读取</th><th>总计</th><th>常用工具</th><th>首条消息</th></tr></thead><tbody id="sessions-body"></tbody></table>
    </div>
    <div id="tab-tasks" class="section">
        <h3 style="margin-bottom:12px;">按任务类型统计</h3>
        <div class="chart-container" id="task-chart"></div>
        <table><thead><tr><th>#</th><th>任务类型</th><th>会话数</th><th>实际消耗</th><th>总 Token</th><th>占比</th></tr></thead><tbody id="tasks-body"></tbody></table>
    </div>
    <div id="tab-tools" class="section">
        <div class="info-box"><strong>说明：</strong>Token 列是将 assistant 消息的 output_tokens 均分给该消息中使用的工具，属于估算值。</div>
        <h3 style="margin-bottom:12px;">TOP 20 工具 Token 消耗</h3>
        <table><thead><tr><th>#</th><th>工具</th><th>调用次数</th><th>归因 Token</th><th>占比</th><th>操作最多的文件</th></tr></thead><tbody id="tools-body"></tbody></table>
    </div>
    <div id="tab-skills" class="section">
        <div class="info-box"><strong>说明：</strong>Skill 上下文字符数总和。估算 Token ≈ 字符数 × 0.3。</div>
        <h3 style="margin-bottom:12px;">TOP 25 Skill 上下文成本</h3>
        <table><thead><tr><th>#</th><th>Skill</th><th>总字符数</th><th>估算 Token</th><th>会话数</th><th>首次加载</th></tr></thead><tbody id="skills-body"></tbody></table>
    </div>
    <div id="tab-daily" class="section">
        <h3 style="margin-bottom:12px;">每日 Token 消耗趋势</h3>
        <div class="chart-container" id="daily-chart"></div>
    </div>
    <div id="tab-heatmap" class="section">
        <h3 style="margin-bottom:12px;">活动热力图</h3>
        <div class="info-box"><strong>说明：</strong>颜色越绿 = 该时段 Claude Code 工具调用越密集。</div>
        <div id="heatmap-container"></div>
    </div>
    <div id="tab-subagents" class="section">
        <h3 style="margin-bottom:12px;">代理（Subagent）花费归因</h3>
        <div class="info-box"><strong>说明：</strong>追踪 Explore/Plan 等子代理的调用次数和 token 开销。Token 数按消息 output_tokens 均分估算。</div>
        <table><thead><tr><th>#</th><th>代理类型</th><th>调用次数</th><th>归因 Token</th><th>占总Token</th><th>预估花费</th><th>最近用途</th></tr></thead><tbody id="subagents-body"></tbody></table>
    </div>
    <div id="tab-models" class="section">
        <h3 style="margin-bottom:12px;">模型花费分布</h3>
        <div class="info-box"><strong>说明：</strong>各模型的消息数量和预估花费。价格为 pricing.json 中的配置。</div>
        <div class="chart-container" id="model-chart"></div>
        <table><thead><tr><th>#</th><th>模型</th><th>消息数</th><th>输入价格</th><th>输出价格</th><th>占比</th><th>估算花费</th></tr></thead><tbody id="models-body"></tbody></table>
    </div>
    <div id="tab-mcptax" class="section">
        <h3 style="margin-bottom:12px;">MCP 上下文税（Context Tax）</h3>
        <div class="info-box"><strong>说明：</strong>MCP 工具定义每轮都占 context。每个工具≈200 token schema 开销。<strong>不用也要付的"房租"。</strong></div>
        <div class="cards" style="padding:0;margin-bottom:12px;" id="mcptax-cards"></div>
        <table><thead><tr><th>#</th><th>MCP Server</th><th>工具数</th><th>每轮开销</th><th>总计(×{total_asst_msgs}轮)</th><th>示例工具</th></tr></thead><tbody id="mcptax-body"></tbody></table>
    </div>
</div>
<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
    <div class="modal" onclick="event.stopPropagation()">
        <button class="close" onclick="closeModal()">&times;</button>
        <h2 id="modalTitle"></h2><div class="sub" id="modalSub"></div>
        <div id="modalTimeline" style="max-height:60vh;overflow-y:auto;"></div>
    </div>
</div>
<script>
const PROJ = {proj_json};
const TIPS = {tips_json};
const PRICING = {pricing_json};
const MCP_TAX = {mcp_tax_json};
const TOTAL_ASST_MSGS = {total_asst_msgs};
{self._js_code()}
</script>
</body></html>"""

    def _js_code(self) -> str:
        return r"""
let currentProj = '_全部项目', searchQuery = '', filteredSessions = [];
function switchProject(name) { currentProj = name; onSearch(); }
function pdata() { return PROJ[currentProj]; }

function onSearch() {
    searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
    const d = pdata();
    let all = [];
    if (d.sessions) { all = d.sessions; }
    else { for (const [pn, pd] of Object.entries(PROJ)) { if (pn === '_全部项目') continue; if (pd.sessions) pd.sessions.forEach(s => { s._proj = pn; all.push(s); }); } }
    if (searchQuery) { all = all.filter(s => { const haystack = (s.task + ' ' + s.first_msg + ' ' + s.date + ' ' + (s._proj||currentProj) + ' ' + Object.keys(s.tools||{}).join(' ') + ' ' + (s.skills||[]).join(' ')).toLowerCase(); return haystack.includes(searchQuery); }); }
    filteredSessions = all;
    document.getElementById('searchHint').textContent = searchQuery ? `匹配 ${all.length} 个会话` : '';
    renderAll();
}

function renderAll() {
    const d = pdata();
    document.getElementById('val-actual').textContent = (d.actual || 0).toLocaleString();
    document.getElementById('val-cacheR').textContent = (d.cache_read || 0).toLocaleString();
    const cr = d.cache_create || 0, crd = d.cache_read || 0;
    document.getElementById('val-hitrate').textContent = ((crd / Math.max(cr+crd,1))*100).toFixed(1) + '%';
    document.getElementById('val-saverate').textContent = ((crd / Math.max((d.input||0)+cr+crd,1))*100).toFixed(1) + '%';
    document.getElementById('val-count').textContent = d.count || 0;
    document.getElementById('val-cacheC').textContent = (cr || 0).toLocaleString();
    document.getElementById('val-cost').textContent = '¥' + ((d.total_cost || 0)).toFixed(2);
    renderTips(); renderSessions(); renderTasks(); renderTools(); renderSkills(); renderDaily(); renderHeatmap();
    renderSubagents(); renderModels(); renderMcpTax();
}

function highlightText(text) {
    if (!searchQuery) return text;
    const escaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return text.replace(new RegExp('(' + escaped + ')', 'gi'), '<span class="highlight">$1</span>');
}

function renderTips() {
    if (!TIPS.length) { document.getElementById('tips-bar').innerHTML = ''; return; }
    const dismissed = JSON.parse(localStorage.getItem('dismissed_tips') || '{}');
    const now = Date.now();
    const active = TIPS.filter(t => { const d = dismissed[t.id]; if (!d) return true; return (now - d) > 14*86400000; });
    if (!active.length) { document.getElementById('tips-bar').innerHTML = ''; return; }
    const colors = { warn: '#fff3cd', info: '#d1ecf1' };
    document.getElementById('tips-bar').innerHTML = active.map(t => `<div style="background:${colors[t.level]||'#d1ecf1'};color:#333;border-radius:6px;padding:8px 14px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;font-size:12px;"><span><strong>${t.title}</strong> — ${t.detail} <span style="color:#0c5460;">(省 ${t.saving})</span></span><button onclick="dismissTip('${t.id}')" style="background:none;border:none;cursor:pointer;font-size:16px;color:#666;">&times;</button></div>`).join('');
}
function dismissTip(id) { const dismissed = JSON.parse(localStorage.getItem('dismissed_tips') || '{}'); dismissed[id] = Date.now(); localStorage.setItem('dismissed_tips', JSON.stringify(dismissed)); renderTips(); }

function renderSessions() {
    let all = filteredSessions.length ? filteredSessions : [];
    if (!all.length) { const d = pdata(); if (d.sessions) all = d.sessions; else for (const [pn, pd] of Object.entries(PROJ)) { if (pn === '_全部项目') continue; if (pd.sessions) pd.sessions.forEach(s => { s._proj = pn; all.push(s); }); } }
    const groupBy = document.getElementById('groupBy')?.value || 'none';
    const sortBy = document.getElementById('sortBy')?.value || 'total';
    const limit = parseInt(document.getElementById('limitBy')?.value || '30');
    let groups = {};
    if (groupBy === 'date') { all.forEach(s => { const key = s.date || '未知日期'; if (!groups[key]) groups[key] = []; groups[key].push(s); }); }
    else if (groupBy === 'task') { all.forEach(s => { const key = s.task || '未分类'; if (!groups[key]) groups[key] = []; groups[key].push(s); }); }
    else { groups['全部会话'] = all; }
    const sortFn = { 'total': (a, b) => b.total - a.total, 'time': (a, b) => (b.ts || '').localeCompare(a.ts || ''), 'count': (a, b) => b.length - a.length }[sortBy] || ((a, b) => b.total - a.total);
    const groupEntries = Object.entries(groups).sort((a, b) => { if (groupBy === 'date') return b[0].localeCompare(a[0]); if (sortBy === 'count') return b[1].length - a[1].length; const sumA = a[1].reduce((s, x) => s + x.total, 0); const sumB = b[1].reduce((s, x) => s + x.total, 0); return sumB - sumA; });
    let totalShown = 0, html = '';
    groupEntries.forEach(([groupName, sessions]) => {
        sessions.sort(sortFn); const limited = limit === 999 ? sessions : sessions.slice(0, limit); totalShown += limited.length;
        const groupTotal = sessions.reduce((s, x) => s + x.total, 0), groupActual = sessions.reduce((s, x) => s + (x.input + x.output), 0);
        if (groupBy !== 'none') { html += `<tr><td colspan="10" style="padding:0;border:none;"><div class="group-header"><span class="group-name">${groupName}</span><span class="group-stats">${sessions.length} 会话 · 实际消耗 ${groupActual.toLocaleString()} · 总计 ${groupTotal.toLocaleString()}</span></div></td></tr>`; }
        limited.forEach((s, i) => {
            const tools = s.tools ? Object.entries(s.tools).sort((a,b)=>b[1].count-a[1].count).slice(0,3) : [];
            const tags = tools.map(([t,td]) => `<span class="tag">${t}(${td.count})</span>`).join(' ');
            const proj = s._proj || currentProj, rowNum = groupBy === 'none' ? (i + 1) : '';
            html += `<tr onclick="showDetail('${s.id}','${proj}')" style="cursor:pointer;" title="点击查看详情"><td>${rowNum}</td><td>${s.date}</td><td>${proj}</td><td>${highlightText(s.task)}</td><td class="num" style="color:#00ba7c;">¥${(s.cost||0).toFixed(2)}</td><td class="num">${(s.input+s.output).toLocaleString()}</td><td class="num">${s.cache_read.toLocaleString()}</td><td class="num">${s.total.toLocaleString()}</td><td>${tags}</td><td class="file-list" title="${s.first_msg}">${highlightText((s.first_msg||'').substring(0,60))}...</td></tr>`;
        });
    });
    document.getElementById('sess-count').textContent = `(${totalShown} 条${groupBy !== 'none' ? ' / ' + all.length + ' 总' : ''})`;
    document.getElementById('sessions-body').innerHTML = html;
}

function renderTasks() {
    const tasks = pdata().tasks; const entries = Object.entries(tasks).sort((a,b)=>b[1].total-a[1].total);
    const maxVal = entries[0]?.[1]?.total || 1, totalAll = entries.reduce((s,e)=>s+e[1].total,0);
    let chart = '', table = '';
    const colors = ['#1d9bf0','#00ba7c','#ffad1f','#8b5cf6','#f91880','#00b4d8','#e67e22','#9b59b6'];
    entries.forEach(([name, data], i) => { const pct = (data.total/maxVal*100).toFixed(1), pctStr = (data.total/totalAll*100).toFixed(1); chart += `<div class="bar-row"><span class="bar-label">${name}</span><div class="bar-fill" style="width:${pct}%;background:${colors[i%colors.length]};">${pctStr}%</div><span class="bar-value">${(data.total/1e6).toFixed(1)}M</span><span class="bar-pct">${data.sessions}会话</span></div>`; table += `<tr><td>${i+1}</td><td>${highlightText(name)}</td><td class="num">${data.sessions}</td><td class="num">${data.actual.toLocaleString()}</td><td class="num">${data.total.toLocaleString()}</td><td class="num">${pctStr}%</td></tr>`; });
    document.getElementById('task-chart').innerHTML = chart; document.getElementById('tasks-body').innerHTML = table;
}

function renderTools() {
    const tools = pdata().tools; const entries = Object.entries(tools).sort((a,b)=>b[1].tokens-a[1].tokens).slice(0,20);
    const actual = pdata().actual || 1; let html = '';
    entries.forEach(([tn, td], i) => { const topF = Object.entries(td.files||{}).sort((a,b)=>b[1]-a[1]).slice(0,3); const files = topF.map(([f,c])=>`${f}(${c})`).join('、'); html += `<tr><td>${i+1}</td><td><code>${highlightText(tn)}</code></td><td class="num">${td.count.toLocaleString()}</td><td class="num">${td.tokens.toFixed(0)}</td><td class="num">${(td.tokens/actual*100).toFixed(1)}%</td><td class="file-list">${highlightText(files||'—')}</td></tr>`; });
    document.getElementById('tools-body').innerHTML = html;
}

function renderSkills() {
    const skills = pdata().skills; const entries = Object.entries(skills).sort((a,b)=>b[1].total_size-a[1].total_size).slice(0,25); let html = '';
    entries.forEach(([sn, sd], i) => { html += `<tr><td>${i+1}</td><td><code>${highlightText(sn)}</code></td><td class="num">${sd.total_size.toLocaleString()}</td><td class="num">${(sd.total_size*0.3).toFixed(0)}</td><td class="num">${sd.sessions}</td><td class="num">${sd.first_sessions}</td></tr>`; });
    document.getElementById('skills-body').innerHTML = html;
}

function renderDaily() {
    const daily = pdata().daily; const entries = Object.entries(daily).sort(); const maxVal = Math.max(...entries.map(e=>e[1].total),1); let html = '';
    entries.forEach(([date, data]) => { const pct = (data.total/maxVal*100).toFixed(1); html += `<div class="bar-row"><span class="bar-label">${date}</span><div class="bar-fill" style="width:${pct}%;background:#1d9bf0;">${data.count}次</div><span class="bar-value">${(data.total/1e6).toFixed(1)}M</span><span class="bar-pct">输入${(data.input/1e6).toFixed(1)}M·输出${(data.output/1e6).toFixed(1)}M</span></div>`; });
    document.getElementById('daily-chart').innerHTML = html;
}

function renderHeatmap() {
    const d = pdata(); const weekHours = Array.from({length:7}, () => Array(24).fill(0)); let allSessions = [];
    if (d.sessions) allSessions = d.sessions; else for (const [pn, pd] of Object.entries(PROJ)) { if (pn === '_全部项目') continue; if (pd.sessions) allSessions = allSessions.concat(pd.sessions); }
    allSessions.forEach(s => { if (!s.ts || !s.hours) return; try { const dow = (new Date(s.ts)).getDay(); s.hours.forEach((c,h)=>{ weekHours[dow][h] += c; }); } catch(e) {} });
    const maxC = Math.max(...weekHours.flat(), 1); const days = ['周日','周一','周二','周三','周四','周五','周六'];
    let html = '<div class="heatmap"><div class="hlabel"></div>';
    for (let h=0; h<24; h++) html += `<div class="hheader">${h}</div>`;
    for (let d=0; d<7; d++) { html += `<div class="hlabel">${days[d]}</div>`; for (let h=0; h<24; h++) { const v = weekHours[d][h], intensity = v / maxC; html += `<div class="hcell" style="background:rgb(${Math.round(13+intensity*10)},${Math.round(22+intensity*180)},${Math.round(25+intensity*10)});" title="${days[d]} ${h}:00 — ${v} 次工具调用"></div>`; } }
    html += '</div>';
    document.getElementById('heatmap-container').innerHTML = html;
}

function renderSubagents() {
    const subs = pdata().subagents || {}; const entries = Object.entries(subs).sort((a,b)=>b[1].tokens-a[1].tokens); const totalTok = Object.values(subs).reduce((s,v)=>s+v.tokens,0) || 1;
    const prices = Object.values(PRICING); const avgPrice = prices.length ? (prices.reduce((s,p)=>s+(p.input||0)+(p.output||0),0)/prices.length/2) : 15;
    let html = '';
    entries.forEach(([name, data], i) => { const cost = (data.tokens / 1e6) * avgPrice; const desc = (data.desc || '').substring(0, 60); html += `<tr><td>${i+1}</td><td><code>${name}</code></td><td class="num">${data.count}</td><td class="num">${data.tokens.toFixed(0)}</td><td class="num">${(data.tokens/totalTok*100).toFixed(1)}%</td><td class="num" style="color:#00ba7c;">¥${cost.toFixed(4)}</td><td class="file-list" title="${desc}">${desc||'—'}</td></tr>`; });
    if (!entries.length) html = '<tr><td colspan="7" style="color:#8b98a5;text-align:center;">暂无子代理调用记录</td></tr>';
    document.getElementById('subagents-body').innerHTML = html;
}

function renderModels() {
    const models = pdata().model_msgs || {}; const entries = Object.entries(models).sort((a,b)=>b[1]-a[1]); const total = entries.reduce((s,e)=>s+e[1],0) || 1; const totalCost = pdata().total_cost || 0;
    const colors = ['#1d9bf0','#00ba7c','#ffad1f','#8b5cf6','#f91880','#00b4d8'];
    let chart = '', table = ''; const maxVal = entries[0]?.[1] || 1;
    entries.forEach(([name, count], i) => { const pct = (count/maxVal*100).toFixed(1); const pctStr = (count/total*100).toFixed(1); const estCost = totalCost * count / total; const p = PRICING[name] || Object.entries(PRICING).find(([k])=>k.toLowerCase()===name.toLowerCase())?.[1] || {}; const inpP = p.input ? '¥'+p.input : '—'; const outP = p.output ? '¥'+p.output : '—'; chart += `<div class="bar-row"><span class="bar-label">${name}</span><div class="bar-fill" style="width:${pct}%;background:${colors[i%colors.length]};">${pctStr}%</div><span class="bar-value">${count} 条</span></div>`; table += `<tr><td>${i+1}</td><td><code>${name}</code></td><td class="num">${count}</td><td class="num">${inpP}</td><td class="num">${outP}</td><td class="num">${pctStr}%</td><td class="num" style="color:#00ba7c;">¥${estCost.toFixed(2)}</td></tr>`; });
    if (!entries.length) table = '<tr><td colspan="7" style="color:#8b98a5;text-align:center;">暂无模型数据</td></tr>';
    document.getElementById('model-chart').innerHTML = chart; document.getElementById('models-body').innerHTML = table;
}

function renderMcpTax() {
    const items = MCP_TAX; let totalPerTurn = items.reduce((s,v)=>s+(v.per_turn||0), 0); let totalAll = items.reduce((s,v)=>s+(v.total_overhead||0), 0);
    document.getElementById('mcptax-cards').innerHTML = `<div class="card" style="border-color:#f91880;"><div class="label">每轮 MCP 税</div><div class="value" style="color:#f91880;">${totalPerTurn.toLocaleString()} tk</div></div><div class="card" style="border-color:#f91880;"><div class="label">总会话轮数</div><div class="value" style="color:#f91880;">${TOTAL_ASST_MSGS.toLocaleString()}</div></div><div class="card" style="border-color:#ffad1f;"><div class="label">总上下文税</div><div class="value" style="color:#ffad1f;">${(totalAll/1e6).toFixed(1)}M tk</div></div>`;
    let html = '';
    items.forEach((item, i) => { const tools = (item.sample_tools||[]).slice(0,3).join(', '); html += `<tr><td>${i+1}</td><td><code>${item.name}</code></td><td class="num">${item.tools}</td><td class="num" style="color:#f91880;">${(item.per_turn||0).toLocaleString()} tk</td><td class="num">${((item.total_overhead||0)/1e6).toFixed(2)}M tk</td><td class="file-list">${tools||'—'}</td></tr>`; });
    document.getElementById('mcptax-body').innerHTML = html;
}

function showDetail(sid, projName) {
    const pd = PROJ[projName] || PROJ['_全部项目']; let session = null;
    const searchIn = pd.sessions || [];
    for (const s of searchIn) { if (s.id === sid) { session = s; break; } }
    if (!session) { for (const [pn, pdx] of Object.entries(PROJ)) { if (pn === '_全部项目') continue; for (const s of (pdx.sessions||[])) { if (s.id === sid) { session = s; break; } } if (session) break; } }
    if (!session) return;
    document.getElementById('modalTitle').textContent = session.task + ' — ' + session.date;
    document.getElementById('modalSub').innerHTML = `实际消耗: <strong>${(session.input+session.output).toLocaleString()}</strong> tokens · 缓存读取: ${session.cache_read.toLocaleString()} · Skills: ${(session.skills||[]).slice(0,8).join(', ') || '无'}`;
    const tl = session.timeline || []; const toolColors = {}; const palette = ['#1d9bf0','#00ba7c','#ffad1f','#8b5cf6','#f91880','#00b4d8','#e67e22','#9b59b6']; let ci = 0;
    let html = tl.length === 0 ? '<p style="color:#8b98a5;">无详细时间线数据</p>' : '';
    tl.forEach(e => { if (!toolColors[e.tool]) { toolColors[e.tool] = palette[ci++ % palette.length]; } html += `<div class="timeline-row"><div class="timeline-dot" style="background:${toolColors[e.tool]};"></div><span class="timeline-hour">${e.h}:00</span><span class="timeline-tool"><code>${e.tool}</code></span><span class="timeline-file">${e.file||'—'}</span><span class="timeline-tok">${e.tok} tok</span></div>`; });
    document.getElementById('modalTimeline').innerHTML = html;
    document.getElementById('modalOverlay').classList.add('show');
}
function closeModal(e) { if (e && e.target !== document.getElementById('modalOverlay')) return; document.getElementById('modalOverlay').classList.remove('show'); }

function exportCSV() {
    let all = filteredSessions.length ? filteredSessions : [];
    if (!all.length) { const d = pdata(); if (d.sessions) all = d.sessions; else for (const [pn, pd] of Object.entries(PROJ)) { if (pn === '_全部项目') continue; if (pd.sessions) pd.sessions.forEach(s => { s._proj = pn; all.push(s); }); } }
    const rows = [['日期','项目','任务类型','花费','Input','Output','实际消耗','缓存读取','缓存创建','总计','首条消息']];
    all.forEach(s => rows.push([s.date, s._proj||currentProj, s.task, (s.cost||0).toFixed(2), s.input, s.output, s.input+s.output, s.cache_read, s.cache_create, s.total, (s.first_msg||'').replace(/,/g,'，')]));
    const csv = rows.map(r => r.map(c => '"'+String(c).replace(/"/g,'""')+'"').join(',')).join('\\n');
    const blob = new Blob(['\\ufeff' + csv], {type:'text/csv;charset=utf-8'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'claude-code-tokens.csv'; a.click(); URL.revokeObjectURL(url);
}

function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const tabs = ['sessions','tasks','tools','skills','daily','heatmap','subagents','models','mcptax'];
    document.querySelectorAll('.tab')[tabs.indexOf(name)].classList.add('active');
    document.getElementById('tab-'+name).classList.add('active');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
renderAll();
"""
