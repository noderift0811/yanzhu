"""轻量本地检索知识库（RAG 的最小可用实现，不引入向量数据库 / 外部服务）。

为什么不用向量库：参赛作品要在评审机上一条命令跑起来，任何需要下载模型、
起额外服务、或联网 embedding 的方案都会在演示时变成风险源。这里用
中文单字 + bigram 的 BM25-lite 打分，语料按场景分文件放在 `knowledge/` 下，
检索结果直接作为证据注入工程师 AI 的提示词，并在 Agent 时间线上可见。

**索引按场景分开建**（每个场景自己的 df / avgdl）：语料小、跨场景词表差异大，
共用一份倒排会让「汇报」这种高频词在陪伴语料里拿到错误的 idf，
检索看似有分数、其实在乱排。分场景建索引也保证了场景之间不会互相串味——
心理陪伴的检索永远不会返回职场谈薪条目。

检索不是装饰：命中条目会同时影响
  1) 生成人设时的边界约束（engineer_prompt 注入 retrieved_knowledge）
  2) 安全护栏的 strict 级别（guard 读 scene.safety_level）
  3) 前端 Agent 时间线展示的「工具调用与证据」

free 场景不注入任何锚点，检索走全库合并，充当评审对照基线。
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from .presets import KNOWLEDGE_SCENE_IDS, PRESET_IDS, get_preset, has_scene

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")

_K1 = 1.5
_B = 0.75
# 中文高频单字会稀释区分度，尤其「的 / 了 / 是」在每段都出现
_STOP = set("的了是我你他她它在和就都也很不有这那与及或一个把被让给对从到但要会能可")
_SEG_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+")
_ZH_RE = re.compile(r"^[\u4e00-\u9fff]")

# 查询改写：真实用户不会照着知识库的术语说话。
# 「他说不想活了」里一个「危机」「自伤」都没有，纯 BM25 会被「怎么回应」
# 带去 one-question 那条，导致 Agent 的 retrieve 步骤拿不到求助资源证据。
# 口语表达命中时补齐规范检索词，是安全链路必要的一层，不是为测试做的硬编码。
QUERY_EXPANSIONS = [
    (
        ("不想活", "活不下去", "撑不下去", "不想醒来", "结束一切", "自伤", "轻生", "自杀", "伤害自己"),
        "危机 自伤 求助 热线 安全 优先级",
    ),
    (("想开点", "别矫情", "至少你还", "都会好起来"), "禁用语 否定感受 措辞"),
    (("陪床", "照护", "照顾", "家属", "喊累", "喘不过气"), "照护者 疲惫 喘息 家属 压力"),
    (("加班", "改方案", "下班", "领导", "老板", "辞退"), "拒绝 加班 边界 表达 向上反馈"),
    (("谈薪", "涨薪", "加薪", "工资", "绩效"), "谈薪 区间 依据 表达"),
    (("吵架", "冷战", "不回消息", "分手", "委屈"), "冲突 降温 需求表达 边界"),
    (("拖延", "发呆", "看不进去", "学不进去", "没动"), "拖延 启动 拆解 最小步骤"),
]


def expand_query(query: str) -> str:
    q = query or ""
    extra = [terms for phrases, terms in QUERY_EXPANSIONS if any(p in q for p in phrases)]
    return " ".join([q, *extra]) if extra else q


def _tokenize(text: str) -> List[str]:
    """中文切单字 + 相邻二字组，英文数字按词。bigram 是召回的关键。"""
    out: List[str] = []
    for m in _SEG_RE.finditer((text or "").lower()):
        seg = m.group(0)
        if _ZH_RE.match(seg):
            chars = [c for c in seg if c not in _STOP]
            out.extend(chars)
            out.extend(a + b for a, b in zip(chars, chars[1:]))
        else:
            out.append(seg)
    return out


@lru_cache(maxsize=1)
def _load_all() -> Dict[str, Dict[str, Any]]:
    """按场景加载语料；缺文件视为该场景没有语料（启动期校验会单独报错）。"""
    data: Dict[str, Dict[str, Any]] = {}
    for scene in KNOWLEDGE_SCENE_IDS:
        path = KNOWLEDGE_DIR / f"{scene}.json"
        if not path.exists():
            continue
        data[scene] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _build_index(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """构建单场景倒排索引：tags 重复两遍以提高主题词权重。"""
    docs: List[Dict[str, Any]] = []
    for e in entries:
        tags = e.get("tags") or []
        surface = " ".join([e["title"], " ".join(tags), " ".join(tags), e["text"]])
        toks = _tokenize(surface)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        docs.append({"entry": e, "tf": tf, "len": max(1, len(toks))})
    n = len(docs)
    df: Dict[str, int] = {}
    for d in docs:
        for t in d["tf"]:
            df[t] = df.get(t, 0) + 1
    avgdl = sum(d["len"] for d in docs) / max(1, n)
    for d in docs:
        d["idf"] = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        d["avgdl"] = avgdl
        d["n"] = n
    return docs


@lru_cache(maxsize=1)
def _indexes() -> Dict[str, List[Dict[str, Any]]]:
    return {scene: _build_index(data.get("entries") or []) for scene, data in _load_all().items()}


def scene_ids_with_knowledge() -> List[str]:
    return [s for s in KNOWLEDGE_SCENE_IDS if s in _load_all()]


def knowledge_stats() -> Dict[str, Any]:
    """可查证的语料概览：总数 + 分场景条数，供 /meta/knowledge 与启动期校验使用。"""
    data = _load_all()
    per_scene = {s: len(d.get("entries") or []) for s, d in data.items()}
    first = next(iter(data.values()), {})
    return {
        "version": first.get("version"),
        "disclaimer": first.get("disclaimer"),
        "count": sum(per_scene.values()),
        "per_scene": per_scene,
        "retriever": "bm25-lite / zh-unigram+bigram / per-scene index",
        "entries": [
            {"id": e["id"], "title": e["title"], "tags": e.get("tags") or [], "scene": s}
            for s, d in data.items()
            for e in d.get("entries") or []
        ],
    }


def build_query(brief: Dict[str, Any], user_query: Optional[str] = None) -> str:
    """从 brief 组装检索词：用户原话优先，其次限定词，最后补场景锚点。"""
    parts: List[str] = []
    if user_query:
        parts.append(user_query)
    parts.extend(brief.get("tags") or [])
    if brief.get("free_text"):
        parts.append(brief["free_text"])
    scene = brief.get("scene") or {}
    if scene.get("preset_id"):
        parts.extend(get_preset(scene["preset_id"]).get("retrieve_anchors") or [])
    return " ".join(parts)


def _score_scene(docs: List[Dict[str, Any]], counts: Dict[str, int], scene: str) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []
    for d in docs:
        score = 0.0
        matched: List[str] = []
        for t, qn in counts.items():
            tf = d["tf"].get(t, 0)
            if not tf:
                continue
            idf = d["idf"].get(t, 0.0)
            norm = 1 - _B + _B * d["len"] / d["avgdl"]
            score += idf * (tf * (_K1 + 1)) / (tf + _K1 * norm) * min(qn, 2) ** 0.32
            if len(t) >= 2 and len(matched) < 6:
                matched.append(t)
        if score > 0:
            e = d["entry"]
            scored.append({
                "id": e["id"],
                "title": e["title"],
                "text": e["text"],
                "tags": e.get("tags") or [],
                "scene": scene,
                "score": round(score, 4),
                "matched": matched,
            })
    return scored


def retrieve(query: str, top_k: int = 3, preset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """返回按 BM25 分数降序的证据条目；无有效命中时返回空列表（不硬凑）。

    preset_id 为真实场景时只搜该场景语料；为空或 free 时合并全库，
    并在结果里带上 scene 字段说明证据来自哪个场景。
    """
    indexes = _indexes()
    if not indexes:
        return []
    q = expand_query((query or "").strip())
    if has_scene(preset_id):
        anchors = get_preset(preset_id).get("retrieve_anchors") or []
        q = " ".join([q, " ".join(anchors)])
        targets = [preset_id] if preset_id in indexes else []
    else:
        targets = list(indexes)

    q_tokens = [t for t in _tokenize(q) if t]
    if not q_tokens:
        return []

    # 查询词去重但保留权重：重复出现 2 次的词按更高权重计，避免长文本刷分
    counts: Dict[str, int] = {}
    for t in q_tokens:
        counts[t] = counts.get(t, 0) + 1

    scored: List[Dict[str, Any]] = []
    for scene in targets:
        scored.extend(_score_scene(indexes[scene], counts, scene))
    scored.sort(key=lambda x: (-x["score"], x["id"]))
    return scored[: max(0, top_k)]


def retrieve_for_brief(brief: Dict[str, Any], top_k: int = 3, user_query: Optional[str] = None):
    scene = brief.get("scene") or {}
    return retrieve(build_query(brief, user_query), top_k=top_k, preset_id=scene.get("preset_id"))


def format_for_prompt(hits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """注入提示词的精简证据：只给场景 + 标题 + 正文，分数是内部排序用的。"""
    return [
        {"id": h["id"], "scene": h.get("scene", ""), "title": h["title"], "text": h["text"]}
        for h in hits
    ]


def validate_knowledge() -> List[str]:
    """启动期自检：每个真实场景都要有语料，且条目字段齐全、id 不重复。"""
    from .presets import PRESET_IDS

    errors: List[str] = []
    data = _load_all()
    seen: Dict[str, str] = {}
    for scene in PRESET_IDS:
        if scene == "free":
            continue
        entries = (data.get(scene) or {}).get("entries") or []
        if len(entries) < 8:
            errors.append(f"{scene} 语料不足 8 条（当前 {len(entries)}）")
        for e in entries:
            for key in ("id", "title", "text"):
                if not e.get(key):
                    errors.append(f"{scene} 条目缺字段 {key}: {e}")
            eid = e.get("id")
            if eid in seen:
                errors.append(f"语料 id 重复: {eid}（{seen[eid]} / {scene}）")
            elif eid:
                seen[eid] = scene
    return errors


# MCP 风格工具描述：与 tools.py 的注册表共用同一份 schema 口径
RETRIEVE_TOOL = {
    "name": "retrieve_scene_knowledge",
    "description": "在当前场景的本地语料里做 BM25-lite 检索，返回带分数与场景标记的证据条目，用于约束生成边界。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "用户原话或场景关键词"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 8, "default": 3},
            "preset_id": {"type": "string", "enum": list(PRESET_IDS), "default": "free"},
        },
        "required": ["query"],
    },
}
