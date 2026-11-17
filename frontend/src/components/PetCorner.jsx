import { useEffect, useRef, useState } from "react";
import { Button, Input, Select, message } from "antd";
import { request } from "../lib/api.js";
import "../styles/pet-corner.css";

const MOODS = [
  { value: "happy", label: "开心 · 尾巴一直摇" },
  { value: "hungry", label: "饿了 · 围着你要吃的" },
  { value: "sleepy", label: "困了 · 缩成一团打盹" },
  { value: "lonely", label: "想你 · 望着门口" },
  { value: "quiet", label: "安静 · 静静待着" },
];

// 宠物角：跟随人格的伙伴状态。核心不在"养"的玩法，而在让状态能进人格提示词——
// 这里改的每一项，后端都会即时反映到下一句对话里（【伙伴状态】块），不耗生成配额。
// ui/hidden：界面偏好（显示开关 + 拖动位置），存人格 spec.pet_ui；沉浸态由外部强制 hidden。
export default function PetCorner({ personaId, hidden = false, ui, onUiChange }) {
  const [pet, setPet] = useState(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const wrapRef = useRef(null);
  const dragRef = useRef(null);
  const movedRef = useRef(false);
  // 拖动中的临时偏移；松手才写回后端，避免每一次 pointermove 都打 PATCH。
  // 同时存一份到 dragRef.cur，pointerup 闭包不必依赖可能陈旧的 draft state。
  const [draft, setDraft] = useState(null);
  const [dragging, setDragging] = useState(false);

  // ui = { hidden, x, y }；x/y 是相对默认右下角的像素偏移，默认 0 保持原位。
  const pos = draft || { x: ui?.x || 0, y: ui?.y || 0 };
  const uiHidden = !!ui?.hidden;

  useEffect(() => {
    let live = true;
    if (!personaId) return () => { live = false; };
    request(`/personas/${personaId}/pet`)
      .then((data) => { if (live) setPet(data); })
      .catch(() => { if (live) setPet(null); });
    return () => { live = false; };
  }, [personaId]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      // antd 的 Select / 下拉渲染到 body 的 portal 里，点它们会被误判成"点了外部"，
      // 导致刚选完心情卡片就关了。这些浮层要排除在外部点击之外。
      if (e.target.closest?.(".ant-select-dropdown, .ant-dropdown, .ant-popover, .ant-message")) return;
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // 拖动：只在 chip（入口按钮）上生效，卡片内部的输入/下拉不受影响。
  const clamp = (v) => Math.max(-2000, Math.min(2000, Math.round(v)));
  const onPointerDown = (e) => {
    if (e.button !== 0) return; // 只响应主键，右键/中键留给浏览器
    dragRef.current = {
      sx: e.clientX, sy: e.clientY,
      ox: ui?.x || 0, oy: ui?.y || 0,
      cur: { x: ui?.x || 0, y: ui?.y || 0 },
    };
    movedRef.current = false;
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    if (Math.abs(dx) + Math.abs(dy) < 3 && !movedRef.current) return; // 手抖阈值
    movedRef.current = true;
    setDragging(true);
    d.cur = { x: clamp(d.ox + dx), y: clamp(d.oy + dy) };
    setDraft(d.cur);
  };
  const onPointerUp = async () => {
    const d = dragRef.current;
    dragRef.current = null;
    setDragging(false);
    if (!d || !movedRef.current) { setDraft(null); return; }
    // 保留 draft 直到写回完成，否则松手瞬间先跳回旧位置、再弹到新位置会闪一下。
    try {
      await onUiChange?.({ hidden: uiHidden, x: d.cur.x, y: d.cur.y });
    } finally {
      setDraft(null);
    }
  };
  // 拖动后浏览器仍会派发一次 click，这里拦掉，避免"拖完顺手打开了卡片"。
  const onChipClick = () => {
    if (movedRef.current) { movedRef.current = false; return; }
    setOpen((v) => !v);
  };

  if (!pet || hidden || uiHidden) return null;

  const change = async (body, successText) => {
    setSaving(true);
    try {
      const updated = await request(`/personas/${personaId}/pet`, { method: "PATCH", body });
      setPet(updated);
      if (successText) message.success(successText);
    } catch (e) {
      message.error(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const checkin = async () => {
    setSaving(true);
    try {
      const updated = await request(`/personas/${personaId}/pet/checkin`, { method: "POST", body: {} });
      setPet(updated);
      if (!updated.checked_in) {
        message.info("今天已经续过火花啦");
      } else if (updated.recalled) {
        message.success(`把你等回来了！${pet.name}断档 ${updated.missed_days} 天，火花重新点亮`);
      } else {
        message.success(`续上第 ${updated.streak} 天火花`);
      }
    } catch (e) {
      message.error(e.message || "续火花失败");
    } finally {
      setSaving(false);
    }
  };

  const moodLabel = MOODS.find((m) => m.value === pet.mood)?.label || "安静 · 静静待着";
  const checkedCount = (pet.calendar || []).filter((d) => d.checked).length;
  const stageHint = {
    together: "今天一直陪着你",
    waiting: "今晚在等你的信",
    dozing: "两天没等到你，打起了盹",
    lost: "几天没见，有点生疏了",
    new: "刚来到你身边",
  }[pet.stage] || pet.stage_text;

  return (
    <div
      className="pf-pet-corner"
      ref={wrapRef}
      style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
    >
      {open && (
        <div className="pf-pet-card">
          <div className="pf-pet-card-head">
            <span className="pf-pet-card-title">伙伴状态</span>
            <span className="pf-pet-card-hint">改动即时进入下一句对话</span>
          </div>
          <div className={`pf-pet-streak is-${pet.stage}`}>
            <span className="pf-pet-streak-num">{pet.streak}<i>天</i></span>
            <span className="pf-pet-streak-text">
              {stageHint} · 最长 {pet.best_streak ?? pet.streak} 天
            </span>
          </div>
          <div className="pf-pet-calendar" aria-label="最近 28 天打卡日历">
            {(pet.calendar || []).map((d) => (
              <span
                key={d.date}
                className={`pf-pet-day${d.checked ? " is-on" : ""}${d.is_today ? " is-today" : ""}`}
                title={`${d.date}${d.checked ? " · 已续火花" : ""}${d.is_today ? " · 今天" : ""}`}
              />
            ))}
          </div>
          <div className="pf-pet-calendar-foot">
            <span>近 28 天续火花 {checkedCount} 次</span>
            <span className="pf-pet-legend"><i /> 已续</span>
          </div>
          <label className="pf-pet-field">
            <span>名字</span>
            <Input
              size="small"
              value={pet.name}
              maxLength={20}
              disabled={saving}
              onChange={(e) => setPet((p) => ({ ...p, name: e.target.value }))}
              onBlur={(e) => { if (e.target.value.trim() && e.target.value !== pet.name) change({ name: e.target.value.trim() }); }}
            />
          </label>
          <label className="pf-pet-field">
            <span>物种</span>
            <Input
              size="small"
              value={pet.species}
              maxLength={20}
              disabled={saving}
              onChange={(e) => setPet((p) => ({ ...p, species: e.target.value }))}
              onBlur={(e) => { if (e.target.value.trim() && e.target.value !== pet.species) change({ species: e.target.value.trim() }); }}
            />
          </label>
          <label className="pf-pet-field">
            <span>此刻心情</span>
            <Select
              size="small"
              value={pet.mood}
              disabled={saving}
              options={MOODS}
              style={{ width: "100%" }}
              onChange={(v) => change({ mood: v })}
            />
          </label>
          <div className="pf-pet-energy">
            <span>活力 {pet.energy}</span>
            <span className="pf-pet-energy-bar"><i style={{ width: `${pet.energy}%` }} /></span>
          </div>
          <div className="pf-pet-card-actions">
            <Button size="small" disabled={saving} onClick={() => change({ feed: true }, `${pet.name}吃饱了`)}>
              喂一次
            </Button>
            <Button
              size="small"
              type="primary"
              disabled={saving}
              onClick={checkin}
            >
              {pet.stage === "together" ? "今天已续" : pet.stage === "lost" || pet.stage === "dozing" ? "召回火花" : "续火花"}
            </Button>
          </div>
          <div className="pf-pet-clause">{pet.prompt_clause}</div>
        </div>
      )}
      <button
        type="button"
        className={`pf-pet-chip is-${pet.stage}${open ? " is-open" : ""}${dragging ? " is-dragging" : ""}`}
        onClick={onChipClick}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-label="拖动可移动，点击查看伙伴状态"
        title="拖动移动位置 · 点击查看伙伴状态"
      >
        <span className="pf-pet-chip-mark" aria-hidden="true">
          <span className="pf-pet-chip-ear" />
          <span className="pf-pet-chip-ear right" />
        </span>
        <span className="pf-pet-chip-body">
          <span className="pf-pet-chip-name">{pet.name}</span>
          <span className="pf-pet-chip-meta">
            {pet.stage === "waiting" ? "在等你的信" : pet.stage === "dozing" ? "打盹中" : pet.stage === "lost" ? "等你召回" : moodLabel.split(" · ")[0]}
            {" · 连续 "}{pet.streak}{" 天"}
          </span>
        </span>
      </button>
    </div>
  );
}
