import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 霓虹街骨架：黑底灯管、发光字、故障闪烁。
// 人格是深夜街角亮着的招牌，用户是推门进来的人——一块招牌，不是聊天窗。
export default function NeonSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "NEON";
  const placeholder = spec.page_copy?.input_placeholder || "敲一下门…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-neon">
      <div className="sk-neon-sign">
        <span className="sk-neon-open">OPEN</span>
        <span className="sk-neon-shop">{name}</span>
        <span className="sk-neon-tube" aria-hidden="true" />
      </div>

      <div className="sk-msgs sk-neon-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-neon-blank">灯管刚通上电。说句话，它会更亮。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-neon-call">
                <span className="sk-neon-tag">[你]</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-neon-line">
                <span className="sk-neon-bar" aria-hidden="true" />
                <p data-content>{m.content}</p>
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-neon-line sk-neon-buzz">
            <span className="sk-neon-tubes" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>

      {error && <div className="sk-error sk-neon-error">{error}</div>}

      <div className="sk-composer sk-neon-composer">
        <span className="sk-neon-prompt">›</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 3 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          推门
        </Button>
      </div>
    </div>
  );
}
