import { useState } from "react";
import { Button, Empty, Input, Space, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";

// 极简对话骨架（M0 唯一实现）。radio / diary / terminal 于 M1 上线，期间回退本骨架。
// 骨架契约：只负责消息区 + 输入区的视觉人格，共用 chrome 由 ChatView 渲染。
export default function MinimalSkeleton({ persona, messages, sending, error, onSend }) {
  const [draft, setDraft] = useState("");
  const spec = persona?.spec || {};
  const placeholder = spec.page_copy?.input_placeholder || "说点什么吧…";
  // 打字指示只在「还没吐出第一个字」时出现；已开始流式则由气泡自身的增长示意
  const showTyping = sending && messages[messages.length - 1]?.role !== "assistant";

  const submit = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };

  return (
    <div className="sk-minimal">
      <div className="sk-msgs">
        {messages.length === 0 && !sending ? (
          <Empty description={spec.page_copy?.greeting || "开始聊天吧"} />
        ) : (
          messages.map((m) => (
            <div key={m.id} data-role={m.role} className={`sk-row sk-row-${m.role}`}>
              <div className={`sk-bubble sk-bubble-${m.role}${m.pending ? " sk-bubble-pending" : ""}`}>
                <Typography.Text className="sk-content" data-content>{m.content}</Typography.Text>
              </div>
            </div>
          ))
        )}
        {showTyping && (
          <div className="sk-row sk-row-assistant">
            <div className="sk-bubble sk-bubble-assistant sk-typing">
              <span className="sk-dot" />
              <span className="sk-dot" />
              <span className="sk-dot" />
            </div>
          </div>
        )}
      </div>
      {error && <div className="sk-error">{error}</div>}
      <div className="sk-composer">
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
          autoSize={{ minRows: 1, maxRows: 5 }}
          disabled={sending}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={submit} loading={sending} disabled={!draft.trim()}>
          发送
        </Button>
      </div>
    </div>
  );
}
