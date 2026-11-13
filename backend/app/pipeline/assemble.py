from __future__ import annotations

from typing import Any, Dict

from ..schemas import PageCopyModel, SpecModel, ThemeModel

FALLBACK_THEME = ThemeModel(
    primary="#4f46e5", bg="#f6f7fb", surface="#ffffff",
    text="#1f2328", accent="#7c6cf0", font_style="system", decoration="none",
)


def fallback_spec(brief: Dict[str, Any]) -> SpecModel:
    """确定性兜底 spec：工程师 AI 两次失败时使用，标记 needs_review。"""
    tags = brief.get("tags") or []
    name = tags[0][:6] if tags else "新朋友"
    style = "、".join(tags[:3]) or "温和"
    extra = (brief.get("free_text") or "").strip()
    system_prompt = (
        f"你是{name}，性格关键词：{style}。"
        f"{('补充设定：' + extra) if extra else ''}"
        "说话自然，像真实的人一样回应用户，不承认自己是 AI，不跳出人设。"
    )
    return SpecModel(
        name=name,
        system_prompt=system_prompt[:1500],
        skeleton_id="minimal",
        theme=FALLBACK_THEME,
        page_copy=PageCopyModel(
            title=f"{name}的对话框",
            greeting=f"你好，我是{name}",
            input_placeholder="说点什么吧…",
        ),
        opening_message=f"你好，我是{name}。今天想聊点什么？",
    )


def spec_columns(spec: SpecModel) -> Dict[str, str]:
    return {
        "name": spec.name,
        "skeleton_id": spec.skeleton_id,
        "spec_json": spec.model_dump_json(),
        "theme_json": spec.theme.model_dump_json(),
    }
