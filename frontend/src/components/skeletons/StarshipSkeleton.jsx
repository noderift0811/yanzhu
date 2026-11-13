import { Button, Input } from "antd";
import { isOpening, isTyping, missionClock, useComposer } from "./shared.js";

// 星舰通讯骨架：深空 HUD、时间码、操作员标签。
// 人格是舰载 AI，用户是值班操作员——一段舰内通讯，不是聊天窗。
export default function StarshipSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "舰载 AI";
  const channel = `CH-${String((persona?.id || "").length || 7).padStart(2, "0")}`;
  const placeholder = spec.page_copy?.input_placeholder || "向舰载系统发送指令…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);
  const last = messages[messages.length - 1];

  return (
    <div className="sk-ship">
      <div className="sk-ship-hud">
        <span className="sk-ship-link">
          <i aria-hidden="true" />
          LINK
        </span>
        <span className="sk-ship-ch">{channel}</span>
        <span className="sk-ship-clock">{missionClock(last?.created_at)}</span>
        <span className="sk-ship-bars" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>

      <div className="sk-msgs sk-ship-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-ship-blank">通讯链路已建立。等待操作员输入。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-ship-line sk-ship-cmd">
                <span className="sk-ship-time">[{missionClock(m.created_at)}]</span>
                <span className="sk-ship-from">OPERATOR</span>
                <span className="sk-ship-text" data-content>{m.content}</span>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-ship-line sk-ship-reply">
                <span className="sk-ship-time">[{missionClock(m.created_at)}]</span>
                <span className="sk-ship-from">{name}</span>
                <span className="sk-ship-text" data-content>{m.content}</span>
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-ship-line sk-ship-reply sk-ship-scanning">
            <span className="sk-ship-time">[···]</span>
            <span className="sk-ship-from">{name}</span>
            <span className="sk-ship-sweep" aria-hidden="true" />
          </div>
        )}
      </div>

      {error && <div className="sk-error sk-ship-error">{error}</div>}

      <div className="sk-composer sk-ship-composer">
        <span className="sk-ship-prompt">OPERATOR ›</span>
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={submit}
          placeholder={placeholder}
          disabled={sending}
          variant="borderless"
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          发送
        </Button>
      </div>
    </div>
  );
}
