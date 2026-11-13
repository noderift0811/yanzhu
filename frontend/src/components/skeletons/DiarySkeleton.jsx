import { useState } from "react";
import { Button, Input } from "antd";

// 手账书信骨架：日记页 + 纸胶带 + 便签。
// 人格是回信的人，用户是贴便签的人——一页手账，不是聊天窗。
function stamp(iso) {
  const d = (iso || "").slice(0, 10);
  return d ? d.replaceAll("-", ".") : "";
}

export default function DiarySkeleton({ persona, messages, sending, error, onSend }) {
  const [draft, setDraft] = useState("");
  const spec = persona?.spec || {};
  const placeholder = spec.page_copy?.input_placeholder || "想跟我说什么呢…";
  const showTyping = sending && messages[messages.length - 1]?.role !== "assistant";

  const submit = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };

  return (
    <div className="sk-diary">
      <div className="sk-msgs sk-diary-msgs">
        {messages.length === 0 && !sending ? (
          <div className="sk-diary-blank">本子还是空的。写下一句，我会回信。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-diary-note">
                <span className="sk-diary-tape" aria-hidden="true" />
                <p data-content>{m.content}</p>
                <span className="sk-diary-stamp">{stamp(m.created_at)}</span>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-diary-page">
                <span className="sk-diary-tape" aria-hidden="true" />
                <p data-content>{m.content}</p>
                <span className="sk-diary-stamp">{stamp(m.created_at)}</span>
              </div>
            )
          )
        )}
        {showTyping && (
          <div className="sk-diary-page sk-diary-writing">
            <span className="sk-diary-tape" aria-hidden="true" />
            <p className="sk-diary-dots">
              <i />
              <i />
              <i />
            </p>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-diary-composer">
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          贴上去
        </Button>
      </div>
    </div>
  );
}
