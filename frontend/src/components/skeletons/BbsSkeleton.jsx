import { Button, Input } from "antd";
import { isOpening, isTyping, useComposer } from "./shared.js";

// 复古论坛骨架：楼层帖、签名档、分隔线。
// 人格是版主/楼主，用户是回帖的人——一个帖子，不是聊天窗。
export default function BbsSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "楼主";
  const board = spec.page_copy?.title || "树洞版";
  const sign = spec.page_copy?.greeting || "—— 此心安处是吾乡";
  const placeholder = spec.page_copy?.input_placeholder || "回帖…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-bbs">
      <div className="sk-bbs-head">
        <span className="sk-bbs-board">◤ 言筑 BBS · {board} ◢</span>
        <span className="sk-bbs-online">在线 1 人</span>
      </div>

      <div className="sk-msgs sk-bbs-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-bbs-blank">本帖还没有人回复。抢占 1 楼。</div>
        ) : (
          messages.map((m, i) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-bbs-post sk-bbs-me">
                <span className="sk-bbs-meta">#{i + 1} · 你</span>
                <p data-content>{m.content}</p>
                <span className="sk-bbs-sign">—— 来自手机客户端</span>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-bbs-post">
                <span className="sk-bbs-meta">
                  #{i + 1} · 楼主 {name}
                </span>
                <p data-content>{m.content}</p>
                <span className="sk-bbs-sign">—— 签名档：{sign}</span>
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-bbs-post sk-bbs-typing">
            <span className="sk-bbs-meta">
              #{messages.length + 1} · 楼主 {name}
            </span>
            <span className="sk-bbs-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-bbs-composer">
        <span className="sk-bbs-prompt">回帖</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          发表
        </Button>
      </div>
    </div>
  );
}
