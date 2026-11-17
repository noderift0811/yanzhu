import { useEffect, useRef, useState } from "react";
import { Button, Input, Modal, Space, Tooltip, message } from "antd";
import { DeleteOutlined, EditOutlined, HolderOutlined } from "@ant-design/icons";
import { request } from "../lib/api.js";
import { compressImage } from "../lib/avatar.js";
import "../styles/decoration.css";

// 自由装饰层：骨架之上叠加用户自己摆放的元件（便签/引言/照片/标牌）。
// 刻意不进骨架本体——16 套骨架是 AI 生成的作品，摆件是用户后加的生活痕迹，
// 两者分层才不会推翻既有视觉。全部用纸感 token + 自带卡片底，深浅骨架都清晰。
export const DECO_TYPES = {
  note: { label: "便签", defaultText: "写点什么吧" },
  quote: { label: "引言", defaultText: "一句喜欢的话" },
  photo: { label: "照片", defaultText: "" },
  badge: { label: "小标牌", defaultText: "我的角落" },
  sticker: { label: "小图案", defaultText: "" },
};

export const STICKER_GLYPHS = {
  flower: "小花", star: "星星", heart: "爱心", leaf: "叶子",
};

// 图案摆件的内联 SVG：不用图片、不用 emoji，深浅骨架下都用固定色，稳定清晰。
function StickerGlyph({ glyph }) {
  const common = { width: 42, height: 42, viewBox: "0 0 48 48", "aria-hidden": true };
  if (glyph === "star") {
    return <svg {...common}><path d="M24 4l5.6 12.2 13.4 1.6-9.9 9.1 2.7 13.2L24 34.4 12.2 40.1l2.7-13.2-9.9-9.1 13.4-1.6z" fill="#e0a458" stroke="#b97a2b" strokeWidth="1.6" strokeLinejoin="round" /></svg>;
  }
  if (glyph === "heart") {
    return <svg {...common}><path d="M24 41S6 29.5 6 17.8C6 11.3 11.3 6 17.8 6c2.9 0 5 1.3 6.2 3.2C25.2 7.3 27.3 6 30.2 6 36.7 6 42 11.3 42 17.8 42 29.5 24 41 24 41z" fill="#d4738f" stroke="#a94c68" strokeWidth="1.6" strokeLinejoin="round" /></svg>;
  }
  if (glyph === "leaf") {
    return <svg {...common}><path d="M39 9C22 9 9 17 9 31c0 4 2 7 5 8 1-13 10-21 22-23-9 4-15 11-17 22 13 1 22-9 22-22 0-2-1-5-2-7z" fill="#7fa86a" stroke="#4f7743" strokeWidth="1.5" strokeLinejoin="round" /></svg>;
  }
  // flower（默认）：五瓣 + 花心
  return (
    <svg {...common}>
      {[0, 72, 144, 216, 288].map((deg) => (
        <ellipse key={deg} cx="24" cy="13.5" rx="6.5" ry="10" fill="#e79bb0" stroke="#b0563a" strokeWidth="1.2"
          transform={`rotate(${deg} 24 24)`} />
      ))}
      <circle cx="24" cy="24" r="6" fill="#e8b64c" stroke="#b0563a" strokeWidth="1.2" />
    </svg>
  );
}

const clamp = (v) => Math.max(0, Math.min(95, v));

// 页面内的摆件渲染 + 拖拽 + 编辑/删除。draft 是拖拽时的本地坐标，pointerup 才提交。
export default function DecorationLayer({ decorations = [], onChange, hidden = false }) {
  const [draft, setDraft] = useState(decorations);
  const [selected, setSelected] = useState(null);
  const [editing, setEditing] = useState(null);
  const [editText, setEditText] = useState("");
  const [editImage, setEditImage] = useState("");
  const [editGlyph, setEditGlyph] = useState("flower");
  const [saving, setSaving] = useState(false);
  const wrapRef = useRef(null);
  const dragRef = useRef(null);
  const movedRef = useRef(false);

  useEffect(() => { setDraft(decorations); }, [decorations]);

  const onPointerDown = (e, deco) => {
    if (e.target.closest(".pf-deco-toolbar")) return;
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = {
      id: deco.id, sx: e.clientX, sy: e.clientY,
      ox: deco.x, oy: deco.y, w: rect.width, h: rect.height,
    };
    movedRef.current = false;
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = ((e.clientX - d.sx) / d.w) * 100;
    const dy = ((e.clientY - d.sy) / d.h) * 100;
    if (Math.abs(dx) + Math.abs(dy) < 0.4) return;
    movedRef.current = true;
    setDraft((prev) => prev.map((x) => (
      x.id === d.id ? { ...x, x: clamp(d.ox + dx), y: clamp(d.oy + dy) } : x
    )));
  };

  const onPointerUp = () => {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d || !movedRef.current) return;
    const moved = draft.find((x) => x.id === d.id);
    if (moved) onChange(draft);
  };

  const openEdit = (deco) => {
    setEditing(deco);
    setEditText(deco.text || "");
    setEditImage(deco.image || "");
    setEditGlyph(deco.glyph || "flower");
  };

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const patch = editing.type === "sticker"
        ? { glyph: editGlyph }
        : { text: editText, image: editImage || undefined };
      const next = draft.map((x) => (
        x.id === editing.id ? { ...x, ...patch } : x
      ));
      await onChange(next);
      setEditing(null);
      message.success("摆件已更新");
    } catch (e) {
      message.error(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    try {
      await onChange(draft.filter((x) => x.id !== id));
      setSelected(null);
      message.success("摆件已移除");
    } catch (e) {
      message.error(e.message || "移除失败");
    }
  };

  const onImage = async (file) => {
    try {
      const url = await compressImage(file);
      setEditImage(url);
    } catch (e) {
      message.error(e.message || "图片处理失败");
    }
  };

  if (hidden || !draft.length) return null;

  return (
    <>
      <div className="pf-deco-layer" ref={wrapRef}>
        {draft.map((d) => (
          <div
            key={d.id}
            className={`pf-deco pf-deco--${d.type}${selected === d.id ? " is-selected" : ""}`}
            style={{ left: `${d.x}%`, top: `${d.y}%` }}
            onPointerDown={(e) => onPointerDown(e, d)}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onClick={() => { if (!movedRef.current) setSelected(selected === d.id ? null : d.id); }}
          >
            <div className="pf-deco-body">
              {d.type === "sticker" ? (
                <span className="pf-deco-sticker"><StickerGlyph glyph={d.glyph || "flower"} /></span>
              ) : d.type === "photo" ? (
                d.image ? <img src={d.image} alt={d.text || "摆件照片"} /> : <span className="pf-deco-ph">点击编辑照片</span>
              ) : d.type === "quote" ? (
                <blockquote>{d.text || DECO_TYPES.quote.defaultText}</blockquote>
              ) : (
                <span>{d.text || DECO_TYPES[d.type]?.defaultText}</span>
              )}
            </div>
            {selected === d.id && (
              <div className="pf-deco-toolbar">
                <Tooltip title="拖动把手移动位置">
                  <span className="pf-deco-handle"><HolderOutlined /></span>
                </Tooltip>
                <button type="button" aria-label="编辑摆件" onClick={(e) => { e.stopPropagation(); openEdit(d); }}>
                  <EditOutlined />
                </button>
                <button type="button" aria-label="删除摆件" onClick={(e) => { e.stopPropagation(); remove(d.id); }}>
                  <DeleteOutlined />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={!!editing}
        onCancel={() => setEditing(null)}
        title={`编辑${editing ? DECO_TYPES[editing.type]?.label : ""}摆件`}
        footer={null}
        width={420}
        destroyOnClose
      >
        {editing && (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            {editing.type === "sticker" ? (
              <label className="pf-deco-edit-field">
                <span>选择图案</span>
                <div className="pf-deco-glyph-picker">
                  {Object.entries(STICKER_GLYPHS).map(([g, label]) => (
                    <button
                      key={g}
                      type="button"
                      className={`pf-deco-glyph-opt${(editGlyph || "flower") === g ? " is-on" : ""}`}
                      onClick={() => setEditGlyph(g)}
                    >
                      <StickerGlyph glyph={g} />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </label>
            ) : editing.type !== "photo" && (
              <label className="pf-deco-edit-field">
                <span>文字内容</span>
                <Input.TextArea
                  rows={3}
                  maxLength={120}
                  showCount
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                />
              </label>
            )}
            {editing.type === "photo" && (
              <label className="pf-deco-edit-field">
                <span>照片（自动压缩为正方形）</span>
                <input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && onImage(e.target.files[0])} />
                {editImage && <img className="pf-deco-edit-preview" src={editImage} alt="预览" />}
              </label>
            )}
            <Button type="primary" block loading={saving} onClick={saveEdit}>保存摆件</Button>
          </Space>
        )}
      </Modal>
    </>
  );
}
