import { useEffect, useState } from "react";
import { Button, Typography } from "antd";
import { useBuildReveal } from "../hooks/useBuildReveal.js";
import { SKELETON_NAMES } from "./skeletons/index.js";
import Avatar from "./Avatar.jsx";

// 建造揭晓：五阶段原地落位（布局 → 上色 → 身份 → 开场 → 就绪）
// 每个阶段展示的都是工程师 AI 的真实产出，非假数据。
function TypingText({ text = "", duration = 2200 }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!text) return undefined;
    const step = Math.max(24, duration / Math.max(text.length, 1));
    const timer = setInterval(() => {
      setN((v) => {
        if (v >= text.length) {
          clearInterval(timer);
          return v;
        }
        return v + 1;
      });
    }, step);
    return () => clearInterval(timer);
  }, [text, duration]);
  return (
    <span>
      {text.slice(0, n)}
      <span className="pf-caret" />
    </span>
  );
}

const SWATCH_KEYS = ["primary", "accent", "bg", "surface", "text"];

export default function BuildReveal({ persona, onDone }) {
  const spec = persona?.spec || {};
  const theme = spec.theme || {};
  const skeletonName = SKELETON_NAMES[spec.skeleton_id] || spec.skeleton_id;
  const { stage, running, labels, skip } = useBuildReveal({ enabled: true, onDone });

  if (!running) return null;

  return (
    <div className="pf-build" style={{ background: theme.bg || "#f6f7fb", color: theme.text || "#1f2328" }}>
      <div className="pf-build-inner">
        <Typography.Text className="pf-build-label">{labels[Math.min(stage, labels.length - 1)]}</Typography.Text>

        {stage >= 1 && (
          <div className="pf-build-stage">
            <div className="pf-build-wire">
              <span className="pf-wire pf-wire-head" />
              <span className="pf-wire pf-wire-body" />
              <span className="pf-wire pf-wire-body" />
              <span className="pf-wire pf-wire-foot" />
            </div>
            <div className="pf-build-note">已选择骨架：{skeletonName}</div>
          </div>
        )}

        {stage >= 2 && (
          <div className="pf-build-stage">
            <div className="pf-build-swatches">
              {SWATCH_KEYS.map((k) => (
                <span key={k} className="pf-swatch" style={{ background: theme[k] }} title={k} />
              ))}
            </div>
            <div className="pf-build-note">主题已配色：{theme.font_style} / {theme.decoration}</div>
          </div>
        )}

        {stage >= 3 && (
          <div className="pf-build-stage pf-build-identity">
            <Avatar name={spec.name} theme={theme} size={64} />
            <div>
              <div className="pf-build-name">{spec.name}</div>
              <div className="pf-build-note">{spec.page_copy?.title}</div>
            </div>
          </div>
        )}

        {stage >= 4 && (
          <div className="pf-build-stage">
            <div className="pf-build-opening">
              <TypingText text={spec.opening_message || ""} />
            </div>
            <div className="pf-build-note">开场白已写入</div>
          </div>
        )}

        {stage >= 5 && <div className="pf-build-stage pf-build-ready">页面就绪，正在进入…</div>}

        <Button size="small" onClick={skip} className="pf-build-skip">
          跳过动画
        </Button>
      </div>
    </div>
  );
}
