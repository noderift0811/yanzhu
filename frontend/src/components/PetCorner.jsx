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
export default function PetCorner({ personaId, hidden = false }) {
  const [pet, setPet] = useState(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const wrapRef = useRef(null);

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

  if (!pet || hidden) return null;

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
      message.success(updated.checked_in ? `续上第 ${updated.streak} 天火花` : "今天已经续过火花啦");
    } catch (e) {
      message.error(e.message || "续火花失败");
    } finally {
      setSaving(false);
    }
  };

  const moodLabel = MOODS.find((m) => m.value === pet.mood)?.label || "安静 · 静静待着";

  return (
    <div className="pf-pet-corner" ref={wrapRef}>
      {open && (
        <div className="pf-pet-card">
          <div className="pf-pet-card-head">
            <span className="pf-pet-card-title">伙伴状态</span>
            <span className="pf-pet-card-hint">改动即时进入下一句对话</span>
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
            <Button size="small" type="primary" disabled={saving} onClick={checkin}>
              续火花
            </Button>
          </div>
          <div className="pf-pet-clause">{pet.prompt_clause}</div>
        </div>
      )}
      <button
        type="button"
        className={`pf-pet-chip${open ? " is-open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-label="查看伙伴状态"
      >
        <span className="pf-pet-chip-mark" aria-hidden="true">
          <span className="pf-pet-chip-ear" />
          <span className="pf-pet-chip-ear right" />
        </span>
        <span className="pf-pet-chip-body">
          <span className="pf-pet-chip-name">{pet.name}</span>
          <span className="pf-pet-chip-meta">{moodLabel.split(" · ")[0]} · 连续 {pet.streak} 天</span>
        </span>
      </button>
    </div>
  );
}
