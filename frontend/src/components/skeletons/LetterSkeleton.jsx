import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer, ymd } from "./shared.js";

// 信笺骨架：横线信纸 + 邮戳 + 落款。
// 人格是写信的人，用户是在页边写批注的人——往复的一封书信，不是聊天窗。
export default function LetterSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "写信的人";
  const placeholder = spec.page_copy?.input_placeholder || "在页边写点什么…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-letter">
      <div className="sk-letter-head">
        <span className="sk-letter-to">致 · 见字如面</span>
        <span className="sk-letter-mark" aria-hidden="true">
          言筑邮
        </span>
      </div>

      <div className="sk-msgs sk-letter-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-letter-blank">纸是新的，等你落下第一笔。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-letter-margin">
                <span className="sk-letter-tag">页边批注</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <article key={m.id} data-role="assistant" className="sk-letter-sheet">
                <p data-content>{m.content}</p>
                <footer className="sk-letter-sign">
                  <span>—— {name}</span>
                  <span className="sk-letter-date">{ymd(m.created_at)}</span>
                </footer>
              </article>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <article className="sk-letter-sheet sk-letter-writing">
            <p className="sk-letter-pen">
              <i />
              <i />
              <i />
            </p>
          </article>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-letter-composer">
        <span className="sk-letter-nib" aria-hidden="true" />
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          落笔
        </Button>
      </div>
    </div>
  );
}
