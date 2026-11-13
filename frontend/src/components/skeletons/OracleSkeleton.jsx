import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 占卜牌骨架：牌阵 + 翻牌 + 解牌。
// 人格是解牌人，用户是问卜者——一次占卜，不是聊天窗。
export default function OracleSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "解牌人";
  const placeholder = spec.page_copy?.input_placeholder || "写下你想问的事…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);
  // 牌序只数解牌回合，问卜者的话不占牌位
  let card = 0;

  return (
    <div className="sk-oracle">
      <div className="sk-oracle-deck">
        <span className="sk-oracle-deck-label">牌阵 · 三张</span>
        <span className="sk-oracle-back" aria-hidden="true" />
        <span className="sk-oracle-back" aria-hidden="true" />
        <span className="sk-oracle-back" aria-hidden="true" />
        <span className="sk-oracle-deck-name">{name}</span>
      </div>

      <div className="sk-msgs sk-oracle-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-oracle-blank">牌已洗好。写下你的问题，我替你翻开。</div>
        ) : (
          messages.map((m) => {
            if (m.role === "user") {
              return (
                <div key={m.id} data-role="user" className="sk-oracle-ask">
                  <span className="sk-oracle-ask-tag">问卜者</span>
                  <p data-content>{m.content}</p>
                </div>
              );
            }
            card += 1;
            return (
              <div key={m.id} data-role="assistant" className="sk-oracle-card">
                <span className="sk-oracle-no">No.{String(card).padStart(2, "0")}</span>
                <p data-content>{m.content}</p>
                <span className="sk-oracle-foot">· {name} 解牌 ·</span>
              </div>
            );
          })
        )}
        {isTyping(messages, sending) && (
          <div className="sk-oracle-card sk-oracle-shuffling">
            <span className="sk-oracle-stack">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-oracle-composer">
        <span className="sk-oracle-prompt">问：</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          翻牌
        </Button>
      </div>
    </div>
  );
}
