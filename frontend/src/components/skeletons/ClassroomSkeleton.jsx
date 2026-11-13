import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 黑板骨架：墨绿板面、粉笔字、粉笔槽。
// 人格是站在讲台上的人，用户是举手提问的学生——一堂课，不是聊天窗。
export default function ClassroomSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "老师";
  const placeholder = spec.page_copy?.input_placeholder || "举手提问…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-board">
      <div className="sk-board-head">
        <span className="sk-board-lesson">第 {messages.length + 1} 课</span>
        <span className="sk-board-teacher">{name} 老师</span>
        <span className="sk-board-chalk" aria-hidden="true" />
      </div>

      <div className="sk-msgs sk-board-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-board-blank">黑板还干净。等一个提问。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-board-ask">
                <span className="sk-board-tag">提问</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-board-write">
                <p data-content>{m.content}</p>
                <span className="sk-board-underline" aria-hidden="true" />
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-board-write sk-board-dust">
            <span className="sk-board-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span className="sk-board-dust-text">正在板书</span>
          </div>
        )}
      </div>

      {error && <div className="sk-error sk-board-error">{error}</div>}

      <div className="sk-board-tray">
        <span className="sk-board-prompt">学生</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 3 }}
          disabled={sending}
          variant="borderless"
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          举手
        </Button>
      </div>
    </div>
  );
}
