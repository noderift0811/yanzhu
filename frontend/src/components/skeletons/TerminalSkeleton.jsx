import { useState } from "react";
import { Button, Input } from "antd";

// 终端骨架：磷光等宽日志流。
// 人格是一个常驻进程，用户是敲命令的访客——一段会话记录，不是聊天窗。
function clock(iso) {
  return (iso || "").slice(11, 16) || "--:--";
}

export default function TerminalSkeleton({ persona, messages, sending, error, onSend }) {
  const [draft, setDraft] = useState("");
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "persona";
  const placeholder = spec.page_copy?.input_placeholder || "输入消息…";
  const showTyping = sending && messages[messages.length - 1]?.role !== "assistant";

  const submit = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };

  return (
    <div className="sk-terminal">
      <div className="sk-msgs sk-term-msgs">
        <div className="sk-term-session">
          <span className="sk-term-line">persona daemon v0.1 — session opened</span>
          <span className="sk-term-line">connected to {name} · 输入 exit 退出（并不会）</span>
        </div>

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} data-role="user" className="sk-term-line sk-term-cmd">
              <span className="sk-term-time">[{clock(m.created_at)}]</span> you@guest:~$ <span data-content>{m.content}</span>
            </div>
          ) : (
            <div key={m.id} data-role="assistant" className="sk-term-line sk-term-out">
              <span className="sk-term-time">[{clock(m.created_at)}]</span> › <span data-content>{m.content}</span>
            </div>
          )
        )}

        {showTyping && (
          <div className="sk-term-line sk-term-out">
            <span className="sk-term-cursor" aria-hidden="true" />
          </div>
        )}
      </div>

      {error && <div className="sk-error sk-term-error">{error}</div>}

      <div className="sk-composer sk-term-composer">
        <span className="sk-term-prompt">you@guest:~$</span>
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={submit}
          placeholder={placeholder}
          disabled={sending}
          variant="borderless"
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          执行
        </Button>
      </div>
    </div>
  );
}
