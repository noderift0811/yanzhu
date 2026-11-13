import { Button, Input } from "antd";
import { hhmm, isOpening, isTyping, useComposer } from "./shared.js";

// 小票骨架：热敏纸、虚线、条码。
// 人格是深夜小店的老板，用户是来点单的客人——一张小票就是一段对话。
export default function ReceiptSkeleton({ persona, messages, sending, error, onSend }) {
  const spec = persona?.spec || {};
  const shop = spec.page_copy?.title || spec.name || persona?.name || "深夜食堂";
  const placeholder = spec.page_copy?.input_placeholder || "今天想吃点什么…";
  const { draft, setDraft, submit, onEnter } = useComposer(onSend, sending);

  return (
    <div className="sk-receipt">
      <div className="sk-receipt-paper">
        <div className="sk-receipt-shop">
          <span className="sk-receipt-shop-name">{shop}</span>
          <span className="sk-receipt-shop-sub">营业至 03:00 · 只收现金</span>
        </div>

        <div className="sk-msgs sk-receipt-msgs">
          {isOpening(messages, sending) ? (
            <div className="sk-receipt-blank">灶还温着。把想吃的写下来。</div>
          ) : (
            messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} data-role="user" className="sk-receipt-order">
                  <span className="sk-receipt-time">{hhmm(m.created_at)}</span>
                  <p data-content>{m.content}</p>
                </div>
              ) : (
                <div key={m.id} data-role="assistant" className="sk-receipt-line">
                  <span className="sk-receipt-time">{hhmm(m.created_at)}</span>
                  <p data-content>{m.content}</p>
                </div>
              )
            )
          )}
          {isTyping(messages, sending) && (
            <div className="sk-receipt-line sk-receipt-wait">
              <span className="sk-receipt-time">--:--</span>
              <p>后厨正在做，稍等…</p>
            </div>
          )}
        </div>

        {error && <div className="sk-error">{error}</div>}

        <div className="sk-receipt-composer">
          <Input.TextArea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onPressEnter={onEnter}
            placeholder={placeholder}
            autoSize={{ minRows: 1, maxRows: 3 }}
            disabled={sending}
          />
          <Button type="primary" onClick={submit} loading={sending} disabled={!draft.trim()}>
            点单
          </Button>
        </div>

        <div className="sk-receipt-foot">
          <span>共计 {messages.length} 条</span>
          <span>谢谢光临</span>
          <div className="sk-receipt-barcode" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
