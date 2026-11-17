import { createPortal } from "react-dom";
import { useEffect, useRef, useState } from "react";
import { ArrowRightOutlined } from "@ant-design/icons";
import "../styles/follow-up.css";

// 豆包式追问气泡：不进骨架的消息数组（那会污染 16 套骨架的渲染与导出），
// 而是用 Portal 挂到骨架消息容器的末尾。这样它跟在最后一条回复后面、
// 随消息区一起滚动，点一下直接把问题发出去。
export default function FollowUpBubbles({ container, questions = [], onPick, disabled = false }) {
  const [target, setTarget] = useState(null);
  const hostRef = useRef(null);

  // container 是 ChatView 里 .pf-chat 的 ref；消息区由骨架渲染，挂载时机晚于本组件，
  // 所以每次 questions 变化都重新查一次 .sk-msgs，拿不到就等下次。
  useEffect(() => {
    if (!questions.length || !container?.current) { setTarget(null); return; }
    const msgs = container.current.querySelector(".sk-msgs");
    setTarget(msgs);
  }, [questions, container]);

  // 挂上去后滚到底，让用户看得到刚追加的按钮。
  useEffect(() => {
    if (target) target.scrollTop = target.scrollHeight;
  }, [target, questions]);

  if (!target || !questions.length) return null;

  return createPortal(
    <div className="pf-followup" aria-label="继续聊的话题建议">
      <div className="pf-followup-label">你可以接着问</div>
      <div className="pf-followup-list">
        {questions.map((q, i) => (
          <button
            key={`${i}-${q}`}
            type="button"
            className="pf-followup-chip"
            disabled={disabled}
            onClick={() => onPick?.(q)}
          >
            {q}
            <ArrowRightOutlined />
          </button>
        ))}
      </div>
    </div>,
    target
  );
}
