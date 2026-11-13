import { useEffect, useMemo, useState } from "react";
import { Button, Modal, Typography, message } from "antd";
import { BgColorsOutlined, UndoOutlined } from "@ant-design/icons";
import { request } from "../lib/api.js";
import { useThemeVars } from "../hooks/useThemeVars.js";
import {
  COLOR_FIELDS,
  DECOR_OPTIONS,
  FONT_OPTIONS,
  THEME_PRESETS,
  contrast,
  contrastGrade,
  derivePalette,
  hexToRgb,
  isDarkTheme,
  readableOn,
  skeletonTone,
} from "../lib/theme.js";
import "../styles/theme-panel.css";

const EDIT_KEYS = COLOR_FIELDS.map((f) => f.key);

// 面板内嵌的迷你预览：在人格库卡片上打开面板时也能当场看到配色效果
function MiniPreview({ theme }) {
  const { style, className } = useThemeVars(theme);
  const bubbleText = readableOn(theme.primary);
  return (
    <div className={`pf-th-prev ${className}`} style={style}>
      <div className="pf-th-prev-bar">
        <i style={{ background: theme.primary }} />
        <span style={{ color: theme.text }}>预览 · 说一句话看看</span>
      </div>
      <div className="pf-th-prev-body">
        <p className="pf-th-prev-a" style={{ background: theme.surface, color: theme.text }}>
          你来得正好，水刚烧开，先坐吧。
        </p>
        <p
          className="pf-th-prev-u"
          style={{ background: theme.primary, color: bubbleText }}
        >
          今天有点累。
        </p>
      </div>
      <div className="pf-th-prev-input" style={{ background: theme.surface }}>
        <span style={{ color: theme.accent }}>写一句话…</span>
        <button type="button" style={{ background: theme.primary, color: bubbleText }}>
          送出
        </button>
      </div>
    </div>
  );
}

// 单个色块 + 十六进制输入；手输非法值时不提交，失焦回填当前值
function ColorRow({ field, value, onChange, note }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);

  const commit = (raw) => {
    const v = raw.startsWith("#") ? raw : `#${raw}`;
    if (hexToRgb(v)) onChange(v.toLowerCase());
    else setText(value);
  };

  return (
    <div className="pf-th-row">
      <label className="pf-th-swatch" style={{ background: value }} title={field.label}>
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={`${field.label}色值`}
        />
      </label>
      <div className="pf-th-meta">
        <span className="pf-th-label">{field.label}</span>
        <span className="pf-th-hint">
          {field.hint}
          {note && <em className="pf-th-row-note">{note}</em>}
        </span>
      </div>
      <input
        className="pf-th-hex"
        value={text}
        spellCheck={false}
        maxLength={7}
        onChange={(e) => setText(e.target.value.trim())}
        onBlur={(e) => commit(e.target.value.trim())}
        onKeyDown={(e) => e.key === "Enter" && commit(e.currentTarget.value.trim())}
        aria-label={`${field.label}十六进制值`}
      />
    </div>
  );
}

// 主题微调：实时预览 + 成套色板 + 逐项微调。不调模型、不耗配额。
export default function ThemePanel({ open, persona, onClose, onPreview, onSaved }) {
  // 聊天页传的是 detail（带 spec.theme），人格库列表传的是 summary（只有 theme）
  const base = persona?.spec?.theme || persona?.theme || null;
  const [theme, setTheme] = useState(base);
  const [presets, setPresets] = useState({});
  const [saving, setSaving] = useState(false);
  const [touched, setTouched] = useState(false);
  // 逐项微调默认收起：首屏只放「成套配色 + 从主色生成」，够用且不用滚动
  const [detailOpen, setDetailOpen] = useState(false);
  // 记住点的是哪套预设（套到固定底色骨架时颜色会被配平，不能再靠色值反查）
  const [appliedPreset, setAppliedPreset] = useState(null);

  // 骨架默认主题：用于「恢复这套骨架的默认配色」
  useEffect(() => {
    if (!open) return;
    request("/meta/skeletons")
      .then((data) => {
        const map = {};
        (data.items || []).forEach((it) => {
          if (it.theme) map[it.id] = it.theme;
        });
        setPresets(map);
      })
      .catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open || !base) return;
    setTheme(base);
    setTouched(false);
    setDetailOpen(false);
    setAppliedPreset(null);
    onPreview?.(base);
    // 只在本面板打开或换了人格时重置，避免 onPreview 引用变化把编辑中的值冲掉
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, persona?.id]);

  // 有些骨架的底色写死在样式里（霓虹的黑、黑板的墨绿），换浅色配色看不出变化。
  // 遇到这类骨架就把配色自动配平到它的明暗方向，保证「点了一定有变化」。
  const tone = skeletonTone(persona?.skeleton_id);
  const lockedTone = tone === "auto" ? null : tone;

  const push = (patch, markTouched = true) => {
    const next = { ...theme, ...patch };
    setTheme(next);
    if (markTouched) {
      setTouched(true);
      setAppliedPreset(null);
    }
    onPreview?.(next);
  };

  // 套用整套配色：固定底色的骨架会先把配色转成同明暗方向
  const applyPreset = (preset) => {
    let target = preset.theme;
    if (lockedTone && (lockedTone === "dark") !== isDarkTheme(preset.theme)) {
      const derived = derivePalette(preset.theme.primary, lockedTone);
      if (derived) {
        target = {
          ...derived,
          font_style: preset.theme.font_style,
          decoration: preset.theme.decoration,
        };
      }
    }
    setTheme(target);
    setTouched(true);
    setAppliedPreset(preset.id);
    onPreview?.(target);
  };

  const dark = theme ? isDarkTheme(theme) : false;
  const ratioText = theme ? contrast(theme.text, theme.bg) : 21;
  const ratioCard = theme ? contrast(theme.text, theme.surface) : 21;
  const grade = contrastGrade(ratioText);
  const danger = ratioText < 3.5;

  const activePreset = useMemo(() => {
    if (!theme) return null;
    if (appliedPreset) return THEME_PRESETS.find((p) => p.id === appliedPreset) || null;
    return (
      THEME_PRESETS.find(
        (p) =>
          p.theme.primary === theme.primary &&
          p.theme.bg === theme.bg &&
          p.theme.text === theme.text
      ) || null
    );
  }, [theme, appliedPreset]);

  const close = () => {
    onPreview?.(null);
    onClose();
  };

  const save = async () => {
    if (!persona || !theme) return;
    const doSave = async () => {
      setSaving(true);
      try {
        const updated = await request(`/personas/${persona.id}`, {
          method: "PATCH",
          body: { theme },
        });
        message.success("配色已保存");
        onPreview?.(null);
        onSaved?.(updated);
      } catch (e) {
        message.error(e.message);
      } finally {
        setSaving(false);
      }
    };
    if (danger) {
      Modal.confirm({
        title: "这套配色可能看不清",
        content: `正文与背景的对比度只有 ${ratioText.toFixed(1)}:1，低于 3.5:1。要保存的话请确认这是有意为之。`,
        okText: "仍然保存",
        cancelText: "回去调",
        onOk: doSave,
      });
      return;
    }
    doSave();
  };

  if (!theme) return null;

  return (
    <Modal
      title={
        <span className="pf-th-title">
          <BgColorsOutlined /> 调整配色
        </span>
      }
      open={open}
      onCancel={close}
      width={440}
      className="pf-th-modal"
      rootClassName="pf-th-root"
      destroyOnClose
      // 对比度护栏与按钮固定在底部：展开逐项微调、滚动到任意位置都能看见
      footer={
        <div className="pf-th-foot">
          <div className={`pf-th-check pf-th-check-${grade.tone}`}>
            <span className="pf-th-check-num">{ratioText.toFixed(1)}:1</span>
            <span>
              正文对比度 · {grade.text}（{grade.level}）
              {ratioCard < 4.5 && (
                <em className="pf-th-check-sub">，卡片上 {ratioCard.toFixed(1)}:1 偏淡</em>
              )}
            </span>
          </div>
          <div className="pf-th-foot-row">
            <button
              type="button"
              className="pf-th-reset"
              disabled={!touched}
              onClick={() => {
                const def = presets[persona?.skeleton_id];
                if (def) {
                  push(def);
                  message.info("已恢复到这套骨架的默认配色");
                } else {
                  push(base);
                }
              }}
            >
              <UndoOutlined /> 恢复默认
            </button>
            <div className="pf-th-foot-btns">
              <Button className="pf-th-cancel" onClick={close}>
                取消
              </Button>
              <Button
                className="pf-th-ok"
                type={danger ? "default" : "primary"}
                danger={danger}
                loading={saving}
                onClick={save}
              >
                保存配色
              </Button>
            </div>
          </div>
        </div>
      }
    >
      <Typography.Paragraph type="secondary" className="pf-th-lead">
        改动会立刻套到页面上，聊天页可以直接看效果。只改配色，不动人设与聊天记录，也不消耗生成次数。
      </Typography.Paragraph>

      <MiniPreview theme={theme} />

      {lockedTone && (
        <p className={`pf-th-lock pf-th-lock-${lockedTone}`}>
          这套骨架固定{lockedTone === "dark" ? "深色" : "浅色"}底，不跟随配色。选
          {lockedTone === "dark" ? "浅" : "深"}色系时会自动配平成
          {lockedTone === "dark" ? "深" : "浅"}底版本，主色与文字仍会变。
        </p>
      )}

      <section className="pf-th-block">
        <div className="pf-th-block-head">
          <span>整套配色</span>
          <em>{activePreset ? `当前：${activePreset.name}` : "已自定义"}</em>
        </div>
        <div className="pf-th-presets">
          {THEME_PRESETS.map((p) => {
            const on = activePreset?.id === p.id;
            return (
              <button
                key={p.id}
                type="button"
                className={`pf-th-preset${on ? " on" : ""}`}
                onClick={() => applyPreset(p)}
                title={`${p.name}：${p.theme.primary} / ${p.theme.bg}`}
              >
                <span className="pf-th-strip">
                  {["bg", "surface", "primary", "accent", "text"].map((k) => (
                    <i key={k} style={{ background: p.theme[k] }} />
                  ))}
                </span>
                <span className="pf-th-preset-name">{p.name}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="pf-th-block">
        <div className="pf-th-block-head">
          <span>从主色生成</span>
          <em>改一个颜色，其余自动配平</em>
        </div>
        <div className="pf-th-gen">
          <label className="pf-th-swatch pf-th-swatch-lg" style={{ background: theme.primary }}>
            <input
              type="color"
              value={theme.primary}
              onChange={(e) => push(derivePalette(e.target.value, dark ? "dark" : "light"))}
              aria-label="主色"
            />
          </label>
          <div className="pf-th-gen-side">
            <span className="pf-th-gen-hex">{theme.primary}</span>
            <div className="pf-th-gen-btns">
              <button
                type="button"
                disabled={lockedTone === "dark"}
                title={lockedTone === "dark" ? "这套骨架固定深色底" : "派生浅色一套"}
                onClick={() => push(derivePalette(theme.primary, "light"))}
              >
                浅底
              </button>
              <button
                type="button"
                disabled={lockedTone === "light"}
                title={lockedTone === "light" ? "这套骨架固定浅色底" : "派生深色一套"}
                onClick={() => push(derivePalette(theme.primary, "dark"))}
              >
                深底
              </button>
            </div>
          </div>
        </div>
      </section>

      <button
        type="button"
        className={`pf-th-more${detailOpen ? " open" : ""}`}
        onClick={() => setDetailOpen((v) => !v)}
        aria-expanded={detailOpen}
      >
        <span>{detailOpen ? "收起逐项微调" : "展开逐项微调"}</span>
        <em>五个色值 · 字体气质 · 背景装饰</em>
      </button>

      <div className={`pf-th-detail${detailOpen ? " open" : ""}`}>
        <section className="pf-th-block">
          <div className="pf-th-block-head">
            <span>逐项微调</span>
            <em>{EDIT_KEYS.length} 个色值</em>
          </div>
          <div className="pf-th-rows">
            {COLOR_FIELDS.map((f) => (
              <ColorRow
                key={f.key}
                field={f}
                value={theme[f.key]}
                onChange={(v) => push({ [f.key]: v })}
                note={lockedTone && f.key === "bg" ? "由这套骨架固定" : ""}
              />
            ))}
          </div>
        </section>

        <section className="pf-th-block">
          <div className="pf-th-block-head">
            <span>字体气质</span>
          </div>
          <div className="pf-th-fonts">
            {FONT_OPTIONS.map((f) => (
              <button
                key={f.value}
                type="button"
                className={`pf-th-font pf-th-font-${f.value}${theme.font_style === f.value ? " on" : ""}`}
                onClick={() => push({ font_style: f.value })}
              >
                {f.sample}
              </button>
            ))}
          </div>
        </section>

        <section className="pf-th-block">
          <div className="pf-th-block-head">
            <span>背景装饰</span>
            <em>纯 CSS，无图片</em>
          </div>
          <div className="pf-th-decors">
            {DECOR_OPTIONS.map((d) => (
              <button
                key={d.value}
                type="button"
                className={`pf-th-decor${theme.decoration === d.value ? " on" : ""}`}
                onClick={() => push({ decoration: d.value })}
              >
                {/* 用 backgroundColor 而不是 background，否则会盖掉 pf-deco-* 的 background-image */}
                <i className={`pf-deco-${d.value}`} style={{ backgroundColor: theme.bg }} />
                <span>{d.label}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </Modal>
  );
}
