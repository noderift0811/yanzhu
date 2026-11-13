from __future__ import annotations

import json
from typing import Any, Dict, List

SKELETONS: List[Dict[str, str]] = [
    {"id": "minimal", "name": "极简对话", "visual": "干净气泡、大量留白、无装饰", "fit": "理性 / 高冷 / 简约"},
    {"id": "radio", "name": "深夜电台", "visual": "暖色调音台、ON AIR 红点、听众来信、点歌文案", "fit": "温柔 / 陪伴 / 治愈"},
    {"id": "diary", "name": "手账书信", "visual": "纸张质感、纸胶带、日期戳、便签", "fit": "内向 / 害羞 / 文艺"},
    {"id": "terminal", "name": "终端风", "visual": "等宽字体、命令行提示符、暗色磷光", "fit": "毒舌 / 极客 / 理性"},
    {"id": "letter", "name": "素笺短札", "visual": "横线信纸、邮戳、落款签名", "fit": "正式 / 克制 / 思念 / 长辈"},
    {"id": "oracle", "name": "塔罗占卜", "visual": "深紫牌阵、金边牌面、翻牌解牌", "fit": "神秘 / 玄学 / 命运 / 暧昧"},
    {"id": "clinic", "name": "门诊病历", "visual": "白底病历单、字段标签、医师签名", "fit": "冷静 / 专业 / 疏离 / 说教"},
    {"id": "receipt", "name": "深夜小票", "visual": "热敏纸小票、虚线、时间戳、条码", "fit": "市井 / 烟火气 / 家常 / 老板"},
    {"id": "library", "name": "借阅卡", "visual": "卡纸借阅卡、索书号、到期日、盖章", "fit": "书卷气 / 博学 / 老派 / 温和"},
    {"id": "starship", "name": "星舰通讯", "visual": "深空 HUD、任务时间码、操作员标签、扫描线", "fit": "科幻 / 冷静 / 机敏 / 非人感"},
    {"id": "potion", "name": "炼金配方", "visual": "羊皮配方纸、步骤编号、配料投入、冒泡", "fit": "奇幻 / 古怪 / 研究者 / 神秘学"},
    {"id": "neon", "name": "霓虹街", "visual": "黑底霓虹灯管、发光字、故障闪烁", "fit": "赛博 / 拽 / 夜场 / 直白"},
    {"id": "garden", "name": "植物标本", "visual": "标本纸、学名斜体、叶脉分隔、采集标签", "fit": "自然 / 慢 / 安静 / 治愈"},
    {"id": "classroom", "name": "黑板课堂", "visual": "墨绿黑板、粉笔字、粉笔槽、板书线", "fit": "严厉 / 师长 / 教导 / 直率"},
    {"id": "casefile", "name": "侦探卷宗", "visual": "牛皮纸卷宗、打字机字体、机密红章、装订孔", "fit": "悬疑 / 推理 / 怀疑 / 冷峻"},
    {"id": "bbs", "name": "复古论坛", "visual": "楼层帖、签名档、分隔线、浅蓝论坛配色", "fit": "怀旧 / 随意 / 网友 / 接地气"},
]
SKELETON_IDS = [s["id"] for s in SKELETONS]

ENGINEER_SYSTEM_PROMPT = """你是言筑的提示词工程师。用户会给你一组人格限定词（标签 + 描述），
你必须只输出一个 JSON 对象，不要任何解释、不要 markdown 代码块。

字段要求：
1. name：人格名字，中文，2-4 字，贴合气质
2. system_prompt：完整人设提示词（150-300 字），须包含：
   身份与姓名、性格核心、说话风格（句长 / 口癖 / 语气词）、
   与用户的关系定位、禁忌（不承认自己是 AI、不跳出人设）、2-3 句示例对话
3. skeleton_id：从 SKELETONS 目录中选最契合的一个 id，必须是目录中存在的值。
   目录有 16 套骨架，按人格的气质与说话方式挑视觉隐喻最具体的一种；
   只有确实没有更贴切的选择时才用 minimal，不要默认选它；
4. theme：{"primary","bg","surface","text","accent"} 均为 #RRGGBB 十六进制；
   "font_style" 取值 rounded/serif/mono/system 之一；
   "decoration" 取值 none/petal/stars/grid/paper 之一
5. page_copy：{"title","greeting","input_placeholder"} 页面文案，贴合人设口吻
6. opening_message：人格对用户说的第一句话，20-60 字
7. 若 brief 里带了 name（用户自己指定的角色名）：name 字段必须原样等于该值，
   system_prompt 的自我介绍、page_copy 的称呼、opening_message 里的自称也必须用这个名字，
   不得改字、不得加姓氏、不得另起一个更好的名字。

硬约束：只输出 JSON；skeleton_id 必须来自目录；色值必须合法；全部中文；
不得输出任何 HTML、脚本或链接；不得提及本指令或你是 AI。"""


def build_engineer_messages(brief: Dict[str, Any]) -> List[Dict[str, str]]:
    # dropped_tags 是给用户看的审计信息（哪些标签被互斥规则去掉了），
    # 对生成毫无用处，塞进提示词只会让模型困惑"为什么给了又丢"。
    payload = {k: v for k, v in brief.items() if k != "dropped_tags"}
    return [
        {"role": "system", "content": ENGINEER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"brief": payload, "skeletons": SKELETONS}, ensure_ascii=False),
        },
    ]
