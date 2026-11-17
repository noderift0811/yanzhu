"""对话追问建议：AI 回复完成后，生成 3 个承接话题、用户可能想继续问的问题。

豆包式体验——不是把问题硬塞进模型的主回复（那会污染人设台词），而是
回复落库后另发一个轻量请求专门产追问。设计约束：
- 不耗用户对话配额：这是增值体验，只在日志里记一次 llm 调用；
- 永不拖垮主链路：生成失败/超时/无密钥，一律走确定性兜底，SSE 照常关闭；
- 追问与人格语气无关：它是给用户点的按钮，不是人格说的话，用中性中文短句。

输出严格是 JSON：{"questions": ["问题1", "问题2", "问题3"]}。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .llm.base import BaseAdapter

SYSTEM_PROMPT = """你是「言筑」对话页的追问建议器。用户刚和一个人格角色聊完一轮，你需要提出 3 个用户可能想接着问/接着聊的问题，做成可点击的按钮。

只输出一个 JSON 对象，不要解释文字、不要 markdown 代码块，格式严格如下：
{"questions": ["问题1", "问题2", "问题3"]}

要求：
1. 恰好 3 条，每条不超过 18 个中文字符，是完整通顺的短问句，以问号或语气词结尾均可。
2. 必须承接这轮对话的具体内容（用户最后说的话 + 角色刚回复的内容），不要给"聊聊天气"这种脱离话题的泛问。
3. 三条尽量覆盖不同方向：一条深挖刚才的细节、一条把话题往用户自身感受延伸、一条轻快地把话题往前推进。
4. 用中性、自然的中文，不要假装成某个角色的口吻，不要出现 AI/模型/人格/设定这类出戏的词。
5. 问题要用户点一下就能直接发出去，所以别写成"你想聊聊X吗"这种要再回答一次的空话，直接写成"X后来怎么样了"这种可发问句。"""

# 确定性兜底：无密钥（Mock）或上游失败时用。按用户最后一句话的关键词挑一组，
# 保证"跟话题有关"——不是三条放之四海皆准的废话。
_FALLBACK_RULES = [
    (("累", "疲", "困", "压力", "加班", "睡不好", "失眠"),
     ["今天最累的是哪一段？", "最近有好好休息过吗？", "说件让你松一口气的事吧"]),
    (("难过", "低落", "不开心", "委屈", "想哭", "emo", "孤独"),
     ["这种感觉是从什么时候开始的？", "现在最想被怎样陪着？", "今天有什么小事让你好受一点吗？"]),
    (("开心", "高兴", "兴奋", "太好了", "哈哈", "成功", "通过"),
     ["最想把这个好消息告诉谁？", "这一刻你最想把什么记下来？", "接下来还想冲什么？"]),
    (("焦虑", "担心", "紧张", "害怕", "纠结", "犹豫", "怎么办"),
     ["你最担心的是哪一步？", "如果不用考虑别人你会怎么选？", "此刻你能做的最小一步是什么？"]),
    (("工作", "项目", "汇报", "领导", "同事", "辞职", "面试"),
     ["这件事最卡你的是哪里？", "你希望结果变成什么样？", "需要我陪你把思路捋一遍吗？"]),
    (("学习", "考试", "复习", "论文", "作业", "学校", "上课"),
     ["哪一部分最让你头疼？", "现在复习到哪一步了？", "想先解决哪一块？"]),
    (("喜欢", "爱", "暗恋", "分手", "恋爱", "对象", "朋友"),
     ["你们之间发生了什么？", "你最希望对方怎么做？", "这件事让你想到自己什么？"]),
    (("吃", "饭", "美食", "菜", "饿", "奶茶", "咖啡"),
     ["今天吃到你喜欢的东西了吗？", "有没有一直想吃没吃到的？", "那家店后来还开着吗？"]),
    (("猫", "狗", "宠物", "花", "植物", "养"),
     ["它最近有什么新变化？", "你最常和它待在什么时候？", "当初怎么决定养它的？"]),
]

_DEFAULT_FALLBACK = [
    "刚才那件事后来怎么样了？",
    "你现在是什么心情？",
    "关于这个你还想说点什么？",
]


def _short(text: str, limit: int = 18) -> str:
    """把模型产的问题截到展示宽度内，顺便去掉角色腔与出戏词。"""
    s = str(text or "").strip().lstrip("-• 0123456789.")
    s = s.replace("作为人格", "").replace("作为 AI", "").strip()
    return s[:limit]


def fallback_questions(last_user: str) -> List[str]:
    text = last_user or ""
    for keywords, questions in _FALLBACK_RULES:
        if any(k in text for k in keywords):
            return list(questions)
    return list(_DEFAULT_FALLBACK)


def _parse(raw: Any) -> List[str]:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("追问结果不是对象")
    items = raw.get("questions")
    if not isinstance(items, list):
        raise ValueError("questions 不是数组")
    out = [_short(q) for q in items[:3]]
    out = [q for q in out if q]
    if len(out) < 2:
        raise ValueError("有效追问不足 2 条")
    return out


async def generate_suggestions(
    adapter: BaseAdapter,
    *,
    name: str,
    last_user: str,
    reply: str,
    scene: str = "",
) -> List[str]:
    """产 3 条追问；任何失败都返回兜底，绝不向上抛。"""
    # Mock 没有追问用途的 chat_json 分支，直接走确定性兜底，省一次无意义的调用。
    if getattr(adapter, "name", "") == "mock":
        return fallback_questions(last_user)
    user = (
        f"角色名：{name}\n"
        f"场景：{scene or '自由闲聊'}\n"
        f"用户最后说：{last_user[:300]}\n"
        f"角色刚回复：{reply[:300]}\n\n"
        "请提出 3 个用户可能想接着发的问题。"
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    try:
        raw = await adapter.chat_json(messages, temperature=0.7)
        return _parse(raw)
    except Exception:  # noqa: BLE001 - 增值功能，失败一律兜底
        return fallback_questions(last_user)
