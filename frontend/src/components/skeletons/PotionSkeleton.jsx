import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 炼金配方骨架：配料投入 + 步骤编号 + 冒泡。
// 人格是配方作者，用户是往坩埚里投料的人——一次炼制，不是聊天窗。
export default function PotionSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "配方作者";
  const placeholder = spec.page_copy?.input_placeholder || "投入一份材料…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  // 步骤号只数助理回合，用户投料不占步骤
  let step = 0;

  return (
    <div className="sk-potion">
      <div className="sk-potion-head">
        <span className="sk-potion-title">配方 · {name}</span>
        <span className="sk-potion-state">
          <i aria-hidden="true" />
          炼制中
        </span>
      </div>

      <div className="sk-msgs sk-potion-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-potion-blank">坩埚已架好，火在下面烧着。</div>
        ) : (
          messages.map((m) => {
            if (m.role === "user") {
              return (
                <div key={m.id} data-role="user" className="sk-potion-throw">
                  <span className="sk-potion-dose">投入 1 份</span>
                  <p data-content>{m.content}</p>
                </div>
              );
            }
            step += 1;
            return (
              <div key={m.id} data-role="assistant" className="sk-potion-step">
                <span className="sk-potion-idx">{String(step).padStart(2, "0")}</span>
                <p data-content>{m.content}</p>
              </div>
            );
          })
        )}
        {isTyping(messages, sending) && (
          <div className="sk-potion-step sk-potion-brewing">
            <span className="sk-potion-idx">{String(step + 1).padStart(2, "0")}</span>
            <span className="sk-potion-bubbles" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-potion-composer">
        <span className="sk-potion-prompt">投料</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          投入
        </Button>
      </div>
    </div>
  );
}
