import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 植物标本骨架：标本纸、学名斜体、叶脉分隔。
// 人格是一份被夹在册子里的标本，用户是采集记录的人——一页标本簿，不是聊天窗。
export default function GardenSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "标本";
  const site = spec.page_copy?.title || "采集地未记录";
  const placeholder = spec.page_copy?.input_placeholder || "记下你此刻看到的东西…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-garden">
      <div className="sk-garden-head">
        <span className="sk-garden-page">标本簿 · 第 {messages.length + 1} 页</span>
        <span className="sk-garden-site">{site}</span>
      </div>

      <div className="sk-msgs sk-garden-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-garden-blank">册子摊开着，等你采集第一份。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-garden-tag">
                <span className="sk-garden-tag-label">采集记录</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-garden-sheet">
                <span className="sk-garden-latin">{name} · specimen</span>
                <p data-content>{m.content}</p>
                <span className="sk-garden-vein" aria-hidden="true" />
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-garden-sheet sk-garden-awaiting">
            <span className="sk-garden-leaves" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-garden-composer">
        <span className="sk-garden-prompt">采集</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          夹进去
        </Button>
      </div>
    </div>
  );
}
