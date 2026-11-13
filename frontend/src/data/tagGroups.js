// 结构化输入：标签分组 + 一键示例（方案第 07 节）
// 标签之间存在语义冲突，全部平铺会让工程师 AI 收到自相矛盾的 brief，
// 最终产出一个人格模糊、没有棱角的角色。这里用「轴」来声明互斥关系，
// 而不是两两配对——四条轴覆盖了原本九对冲突，新标签挂到轴上就自动生效。
export const TAG_GROUPS = [
  {
    key: "temperament",
    label: "性格基调",
    tags: ["内向", "外向", "高冷", "温柔", "毒舌", "粘人", "理性", "感性", "傲娇", "慢热"],
  },
  {
    key: "tone",
    label: "语气",
    tags: ["活泼", "沉稳", "腼腆", "冷淡", "撒娇", "严肃", "俏皮", "安静"],
  },
  {
    key: "relation",
    label: "关系定位",
    tags: ["笔友", "前辈", "青梅竹马", "管家", "同桌", "树洞", "对手"],
  },
  {
    key: "taboo",
    label: "禁区",
    tags: ["不说教", "不玩梗", "不主动提问", "不长篇大论", "不客气"],
  },
];

// 互斥轴：同一轴最多选一个。轴内的成员是同一维度的不同位置，不可能同时成立。
export const AXES = [
  { key: "social", label: "社交向", members: ["内向", "外向"] },
  { key: "judge", label: "判断式", members: ["理性", "感性"] },
  { key: "energy", label: "能量", members: ["活泼", "安静", "沉稳", "冷淡"] },
  { key: "measure", label: "分寸", members: ["严肃", "俏皮", "撒娇"] },
];
// 关系定位不进轴：它靠 GROUP_QUOTA.relation = 1 单选取代，
// 这样「青梅竹马 + 同桌」这类需要额外说明的组合（两人本就该是同一人）
// 会被配额挡住，而不是被写死在轴里，日后想放开只改数字即可。

// 反差张力：看着冲突其实是加分项（嘴硬心软、外冷内热），不禁用，
// 只在补充描述为空时提醒一句——用户自己写清了怎么调和就不再打扰。
export const TENSIONS = [
  { pair: ["毒舌", "温柔"], note: "嘴硬心软很出彩，但要写清什么时候会软下来" },
  { pair: ["高冷", "粘人"], note: "反差萌，建议点明对谁冷、对谁粘" },
  { pair: ["高冷", "温柔"], note: "外冷内热，建议写清冷与热的切换条件" },
  { pair: ["慢热", "粘人"], note: "慢热到粘人的过渡点值得写一句" },
  { pair: ["腼腆", "撒娇"], note: "小声撒娇是加分项，写清什么情况下会这样" },
  { pair: ["傲娇", "粘人"], note: "傲娇的粘人通常是别扭的，写清表现形式" },
  { pair: ["内向", "活泼"], note: "内心安静但表达活跃，建议说明是文字里活泼还是熟了才活泼" },
];

// 分组配额：只约束上限，下限交给「至少选一个」的整体校验。
// 禁区不设组上限——"不说教 + 不玩梗 + 不主动提问"是叠加的约束，彼此不冲突，
// 多选只会让人格更准确；总量由 TOTAL_MAX 兜住。
export const GROUP_QUOTA = { temperament: 3, tone: 2, relation: 1 };
export const TOTAL_MAX = 8;

export const GROUP_LABEL = Object.fromEntries(TAG_GROUPS.map((g) => [g.key, g.label]));

// 标签 → 所属分组 key
export function groupOf(tag) {
  const g = TAG_GROUPS.find((grp) => grp.tags.includes(tag));
  return g ? g.key : null;
}

// 标签 → 它所在的轴（理论上一条，容错返回多条）
export function axesOf(tag) {
  return AXES.filter((ax) => ax.members.includes(tag));
}

// 给定已选标签，算出每个未选标签被哪条轴上的谁挡住
// 返回 { 标签: "与「内向」互斥" }
export function blockedMap(tags) {
  const blocked = {};
  for (const ax of AXES) {
    const chosen = ax.members.filter((m) => tags.includes(m));
    if (!chosen.length) continue;
    for (const m of ax.members) {
      if (!tags.includes(m)) blocked[m] = `与「${chosen[0]}」互斥`;
    }
  }
  return blocked;
}

// 组配额是否已满 → { temperament: true, ... }
export function groupFullMap(tags) {
  const count = {};
  for (const t of tags) {
    const g = groupOf(t);
    if (g) count[g] = (count[g] || 0) + 1;
  }
  const full = {};
  for (const [g, max] of Object.entries(GROUP_QUOTA)) full[g] = (count[g] || 0) >= max;
  return full;
}

// 确定性校正：同轴保留先出现的，组配额超出丢弃靠后的。
// 用于两处——老数据回填到编辑器、以及提交前的最后一道自检。
export function sanitizeTags(tags) {
  const kept = [];
  const dropped = [];
  const usedAxes = new Set();
  for (const tag of tags) {
    if (kept.includes(tag)) continue;
    const ax = axesOf(tag).find((a) => usedAxes.has(a.key));
    if (ax) {
      const winner = ax.members.find((m) => kept.includes(m));
      dropped.push({ tag, reason: `与「${winner}」互斥` });
      continue;
    }
    const g = groupOf(tag);
    if (g && GROUP_QUOTA[g] !== undefined) {
      const n = kept.filter((k) => groupOf(k) === g).length;
      if (n >= GROUP_QUOTA[g]) {
        dropped.push({ tag, reason: `「${GROUP_LABEL[g]}」最多 ${GROUP_QUOTA[g]} 个` });
        continue;
      }
    }
    if (kept.length >= TOTAL_MAX) {
      dropped.push({ tag, reason: `最多选 ${TOTAL_MAX} 个标签` });
      continue;
    }
    kept.push(tag);
    axesOf(tag).forEach((a) => usedAxes.add(a.key));
  }
  return { tags: kept, dropped };
}

// 命中的反差张力对（只返回涉及已选标签的）
export function tensionHits(tags) {
  return TENSIONS.filter((t) => t.pair.every((p) => tags.includes(p)));
}

export const EXAMPLES = [
  {
    label: "内向害羞的笔友",
    tags: ["内向", "腼腆", "笔友", "安静"],
    free_text: "说话轻声细语，句末常带省略号，熟了会小声撒娇",
  },
  {
    label: "毒舌但可靠的前辈",
    tags: ["毒舌", "理性", "前辈", "不说教"],
    free_text: "嘴上不饶人但给出的建议都很准，偶尔嘴硬心软",
  },
];
