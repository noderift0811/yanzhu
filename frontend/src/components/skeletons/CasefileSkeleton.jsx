import { Button, Input } from "antd";
import { docNo, isOpening, isTyping, useComposer } from "./shared.js";

// 卷宗骨架：牛皮纸、打字机字体、机密红章、装订孔。
// 人格是主办这件案子的人，用户是来补充线索的人——一份卷宗，不是聊天窗。
export default function CasefileSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "主办人";
  const placeholder = spec.page_copy?.input_placeholder || "补充你掌握的情况…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);
  // 卷宗条目与线索各自编号，避免用消息下标导致跳号
  let docIdx = 0;
  let noteIdx = 0;

  return (
    <div className="sk-case">
      <div className="sk-case-head">
        <span className="sk-case-no">CASE No. {docNo(persona)}</span>
        <span className="sk-case-owner">{name}</span>
        <span className="sk-case-secret">机密</span>
      </div>

      <div className="sk-msgs sk-case-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-case-blank">卷宗摊开在第一页，等你写下第一条线索。</div>
        ) : (
          messages.map((m) => {
            if (m.role === "user") {
              noteIdx += 1;
              return (
                <div key={m.id} data-role="user" className="sk-case-note">
                  <p data-content>{m.content}</p>
                  <span className="sk-case-note-by">线索 {String(noteIdx).padStart(2, "0")} · 提供人</span>
                </div>
              );
            }
            docIdx += 1;
            return (
              <div key={m.id} data-role="assistant" className="sk-case-doc">
                <span className="sk-case-lineno">{String(docIdx).padStart(2, "0")}</span>
                <p data-content>{m.content}</p>
              </div>
            );
          })
        )}
        {isTyping(messages, sending) && (
          <div className="sk-case-doc sk-case-typing">
            <span className="sk-case-hammer" aria-hidden="true" />
            <span className="sk-case-typing-text">正在记录</span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-case-composer">
        <span className="sk-case-prompt">线索</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          归档
        </Button>
      </div>
    </div>
  );
}
