import { useState } from "react";
import { Button, Input } from "antd";
import { AudioOutlined } from "@ant-design/icons";

// 深夜电台骨架：主播口播 + 听众来信 + 调音台。
// 人格是深夜电台的主持人，用户是拨热线点歌的听众——不是聊天窗，是一档节目。
function clock(iso) {
  return (iso || "").slice(11, 16) || "--:--";
}

export default function RadioSkeleton({ persona, messages, sending, error, onSend }) {
  const [draft, setDraft] = useState("");
  const spec = persona?.spec || {};
  const placeholder = spec.page_copy?.input_placeholder || "点一首歌，或者说说话…";
  const showTyping = sending && messages[messages.length - 1]?.role !== "assistant";

  const submit = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };

  return (
    <div className="sk-radio">
      <div className="sk-radio-console">
        <span className="sk-radio-onair">
          <i className="sk-radio-dot" aria-hidden="true" />
          ON AIR
        </span>
        <span className="sk-radio-freq">FM 87.5 · 深夜频道</span>
        <span className="sk-radio-eq" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
          <i />
        </span>
        <span className="sk-radio-listeners">正在收听：1 人</span>
      </div>

      <div className="sk-msgs sk-radio-msgs">
        {messages.length === 0 && !sending ? (
          <div className="sk-radio-silence">今晚的电波刚搭好，说点什么把它唤醒。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-radio-letter">
                <span className="sk-radio-tag">听众来信 · {clock(m.created_at)}</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-radio-bubble">
                <span className="sk-radio-tag">主播 · {clock(m.created_at)}</span>
                <p data-content>{m.content}</p>
              </div>
            )
          )
        )}
        {showTyping && (
          <div className="sk-radio-bubble sk-radio-loading">
            <span className="sk-radio-tag">主播</span>
            <p className="sk-radio-wave">
              <i />
              <i />
              <i />
              <i />
            </p>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-radio-composer">
        <span className="sk-radio-callsign">热线</span>
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
        <Button type="primary" icon={<AudioOutlined />} onClick={submit} loading={sending} disabled={!draft.trim()}>
          送出电波
        </Button>
      </div>
    </div>
  );
}
