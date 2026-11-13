import { useEffect } from "react";
import { Input, Typography, message } from "antd";
import {
  TAG_GROUPS,
  TOTAL_MAX,
  GROUP_QUOTA,
  GROUP_LABEL,
  blockedMap,
  groupFullMap,
  groupOf,
  sanitizeTags,
  tensionHits,
} from "../data/tagGroups.js";

// 标签点选编辑器：向导与"重新生成"弹窗共用
// 互斥有三层：同轴直接置灰、组配额置灰、反差组合只提示不禁用。
export default function TagEditor({ value, onChange }) {
  const { tags, free_text: freeText } = value;
  const blocked = blockedMap(tags);
  const groupFull = groupFullMap(tags);
  const tensions = tensionHits(tags);

  // 老数据回填（人格库里已存在的人格可能带着冲突标签）：进编辑器时静默校正一次。
  // sanitizeTags 幂等，没有冲突就不会触发 onChange，不会打转。
  useEffect(() => {
    const { tags: safe, dropped } = sanitizeTags(tags);
    if (dropped.length) onChange({ ...value, tags: safe });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tags]);

  const toggle = (tag) => {
    // 不用 disabled：disabled 会吞掉点击，移动端没有 hover，用户只会觉得"点不动"
    // 却不知道为什么。留可点、点了给一句解释，比一个死按钮有用。
    if (blocked[tag]) {
      message.info(`${tag} ${blocked[tag]}，已为你保留先选的那个`);
      return;
    }
    const key = groupOf(tag);
    if (groupFull[key] && !tags.includes(tag)) {
      message.info(`「${GROUP_LABEL[key]}」最多 ${GROUP_QUOTA[key]} 个，先取消一个再选`);
      return;
    }
    const next = tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag];
    onChange({ ...value, tags: next });
  };

  const countOf = (key) => tags.filter((t) => groupOf(t) === key).length;

  return (
    <div className="pf-tag-editor">
      <div className="pf-tag-total">
        已选 <b>{tags.length}</b> / {TOTAL_MAX}
        {tags.length >= TOTAL_MAX && <span className="pf-tag-total-hint">已达上限</span>}
      </div>
      {TAG_GROUPS.map((group) => {
        const cap = GROUP_QUOTA[group.key];
        const used = countOf(group.key);
        const full = groupFull[group.key];
        return (
          <div key={group.key} className="pf-tag-group">
            <Typography.Text type="secondary" className="pf-tag-group-label">
              {group.label}
              {cap !== undefined && (
                <span className={`pf-tag-cap${full ? " pf-tag-cap-full" : ""}`}>
                  {used}/{cap}
                </span>
              )}
            </Typography.Text>
            <div className="pf-tag-row">
              {group.tags.map((tag) => {
                const on = tags.includes(tag);
                // 互斥优先于配额：先说清"和谁冲突"，比只说"满了"有用
                const why = !on && (blocked[tag] || (full ? `「${group.label}」最多 ${cap} 个` : ""));
                return (
                  <button
                    key={tag}
                    type="button"
                    className={`pf-tag${on ? " pf-tag-on" : ""}${why ? " pf-tag-blocked" : ""}`}
                    onClick={() => toggle(tag)}
                    // 不用 aria-disabled / disabled：这个按钮确实响应点击（给一句解释），
                    // 标成 disabled 会让屏幕阅读器与自动化工具认定它不可操作，与事实不符。
                    title={why || undefined}
                    aria-pressed={on}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      {tensions.length > 0 && !freeText.trim() && (
        <div className="pf-tag-tension">
          {tensions.map((t) => (
            <div key={t.pair.join("+")}>
              「{t.pair[0]}」＋「{t.pair[1]}」是反差设定：{t.note}
            </div>
          ))}
        </div>
      )}
      <Input.TextArea
        value={freeText}
        onChange={(e) => onChange({ ...value, free_text: e.target.value.slice(0, 200) })}
        placeholder="补充描述（可选，200 字以内）：说话风格、口癖、禁忌……"
        autoSize={{ minRows: 2, maxRows: 5 }}
        maxLength={200}
        showCount
      />
    </div>
  );
}
