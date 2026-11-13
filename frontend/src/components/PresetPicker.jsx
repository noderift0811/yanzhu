import { useEffect, useState } from "react";
import { Tag, Typography } from "antd";
import { request } from "../lib/api.js";

// 场景预设：不是「换一套皮肤」，而是换一条 AI 主链路的输入。
// 选 care 会同时改变检索语料、规划约束、护栏级别与生成的页面形态。
export default function PresetPicker({ value, onChange }) {
  const [items, setItems] = useState([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    request("/meta/presets")
      .then((d) => {
        if (alive) setItems(d.items || []);
      })
      .catch(() => {
        // 元数据接口不可用时静默隐藏预设区，自由创作入口仍然可用
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (failed || items.length === 0) return null;

  return (
    <div className="ag-presets">
      <div className="ag-presets-head">
        <Typography.Text strong>先选一个场景（可跳过）</Typography.Text>
        <Typography.Text type="secondary" className="ag-presets-hint">
          场景会驱动检索 → 规划 → 生成 → 校验 → 兜底五步链路，由 AI 决定界面形态，不是换皮肤。
        </Typography.Text>
      </div>
      <div className="ag-presets-grid">
        {items.map((p) => {
          const selected = p.id === "free" ? !value : value?.id === p.id;
          return (
            <button
              type="button"
              key={p.id}
              className={`ag-preset${selected ? " is-active" : ""}`}
              style={{ "--ag-accent": p.accent }}
              onClick={() => onChange(p.id === "free" ? null : p)}
              aria-pressed={selected}
            >
              <span className="ag-preset-bar" />
              <span className="ag-preset-title">{p.name}</span>
              <span className="ag-preset-sub">{p.subtitle}</span>
              <span className="ag-preset-dir">{p.direction}</span>
              <span className="ag-preset-tags">
                {(p.tags || []).length ? (
                  p.tags.slice(0, 4).map((t) => <Tag key={t} className="ag-preset-tag">{t}</Tag>)
                ) : (
                  <span className="ag-preset-empty">不限定标签，自由填写</span>
                )}
              </span>
              {p.sample_prompt && <span className="ag-preset-sample">演示输入：{p.sample_prompt}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
