import { Button, Input } from "antd";
import { docNo, isOpening, isTyping, useComposer, ymd } from "./shared.js";

// 借书卡骨架：卡纸、索书号、到期日戳。
// 人格是一本被借出的书，用户是借阅人——一次借阅记录，不是聊天窗。
export default function LibrarySkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "馆藏";
  const placeholder = spec.page_copy?.input_placeholder || "写一句你想问这本书的话…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-lib">
      <div className="sk-lib-head">
        <span className="sk-lib-org">言筑图书馆 · 借阅卡</span>
        <span className="sk-lib-callno">索书号 {docNo(persona)}</span>
      </div>

      <div className="sk-msgs sk-lib-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-lib-blank">卡片还是空白的。写下第一笔借阅。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-lib-slip">
                <span className="sk-lib-slip-tag">借书条</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-lib-card">
                <div className="sk-lib-card-top">
                  <span className="sk-lib-book">{name}</span>
                  <span className="sk-lib-due">归还 {ymd(m.created_at)}</span>
                </div>
                <p data-content>{m.content}</p>
                <span className="sk-lib-rule" aria-hidden="true" />
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-lib-card sk-lib-stamping">
            <span className="sk-lib-stamp" aria-hidden="true" />
            <span className="sk-lib-stamping-text">盖章中…</span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-lib-composer">
        <span className="sk-lib-prompt">借阅人</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          登记
        </Button>
      </div>
    </div>
  );
}
