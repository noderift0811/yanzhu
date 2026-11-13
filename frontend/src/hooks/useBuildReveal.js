import { useCallback, useEffect, useRef, useState } from "react";

// 建造揭晓：单次调用拿到全量 spec 后，按真实决策顺序分阶段落位。
// 硬规则：禁 location.reload（原地热替换）；总时长封顶约 10s（本编排约 5.7s）。
const STAGE_MS = [900, 900, 900, 2400, 600]; // 布局 → 上色 → 身份 → 开场 → 就绪
const STAGE_LABELS = [
  "AI 正在选择骨架…",
  "AI 正在调配主题…",
  "AI 正在生成身份…",
  "AI 正在写下开场白…",
  "页面就绪",
];
const TOTAL = STAGE_MS.reduce((a, b) => a + b, 0) + 400;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function useBuildReveal({ enabled = true, onDone }) {
  const [stage, setStage] = useState(enabled ? 0 : STAGE_MS.length);
  const [running, setRunning] = useState(!!enabled);
  const timers = useRef([]);
  const doneRef = useRef(false);

  const finish = useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setStage(STAGE_MS.length);
    setRunning(false);
    onDone?.();
  }, [onDone]);

  useEffect(() => {
    if (!enabled || prefersReducedMotion()) {
      finish();
      return;
    }
    let acc = 0;
    STAGE_MS.forEach((ms, i) => {
      acc += ms;
      timers.current.push(setTimeout(() => setStage(i + 1), acc));
    });
    timers.current.push(setTimeout(finish, acc + 400));
    return () => timers.current.forEach(clearTimeout);
  }, [enabled, finish]);

  return { stage, running, labels: STAGE_LABELS, total: TOTAL, skip: finish };
}
