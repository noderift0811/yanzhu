import { Button, Input } from "antd";
import { docNo, isOpening, isTyping, useComposer } from "./shared.js";

// 病历骨架：门诊记录单，字段化的冷静语气。
// 人格是接诊医师，用户是就诊者——一次问诊，不是聊天窗。
export default function ClinicSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const name = spec.name || persona?.name || "接诊医师";
  const dept = spec.page_copy?.title || "全科门诊";
  const placeholder = spec.page_copy?.input_placeholder || "描述你的症状…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-clinic">
      <div className="sk-clinic-head">
        <span className="sk-clinic-title">门诊记录</span>
        <span className="sk-clinic-no">No. {docNo(persona)}</span>
        <span className="sk-clinic-dept">{dept}</span>
      </div>

      <div className="sk-msgs sk-clinic-msgs">
        {isOpening(messages, sending) ? (
          <div className="sk-clinic-blank">候诊区空着。说说哪里不舒服。</div>
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} data-role="user" className="sk-clinic-entry">
                <span className="sk-clinic-label">患者自述</span>
                <p data-content>{m.content}</p>
              </div>
            ) : (
              <div key={m.id} data-role="assistant" className="sk-clinic-sheet">
                <span className="sk-clinic-label">医师处置</span>
                <p data-content>{m.content}</p>
                <span className="sk-clinic-sign">— {name} 医师</span>
              </div>
            )
          )
        )}
        {isTyping(messages, sending) && (
          <div className="sk-clinic-sheet sk-clinic-busy">
            <span className="sk-clinic-label">书写中</span>
            <span className="sk-clinic-caret" aria-hidden="true" />
          </div>
        )}
      </div>

      {error && <div className="sk-error">{error}</div>}

      <div className="sk-composer sk-clinic-composer">
        <span className="sk-clinic-prompt">主诉</span>
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onPressEnter={onEnter}
          placeholder={placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={sending}
        />
        <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
          提交
        </Button>
      </div>
    </div>
  );
}
