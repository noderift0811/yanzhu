import { useCallback, useEffect, useRef, useState } from "react";
import { request, streamSSE } from "../lib/api.js";

// M1：SSE 流式（fetch ReadableStream 逐 token 追加）。
// 事件序列：meta（用户消息落库）→ token* → done（助手消息 + 配额）；
// error 事件表示上游失败，后端已回滚用户消息，前端同步清理占位。
export function useChat({ conversationId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const loadSeq = useRef(0);

  const load = useCallback(async (cid) => {
    if (!cid) {
      setMessages([]);
      return;
    }
    // 序号守卫：快速切换会话时，旧会话的迟到响应不得覆盖新会话
    const seq = ++loadSeq.current;
    setLoading(true);
    setError(null);
    try {
      const data = await request(`/conversations/${cid}/messages?limit=50`);
      if (seq !== loadSeq.current) return;
      setMessages(data.items || []);
    } catch (e) {
      if (seq !== loadSeq.current) return;
      setError(e.message);
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(conversationId);
  }, [conversationId, load]);

  const send = useCallback(
    async (content) => {
      const text = (content || "").trim();
      if (!text || !conversationId || sending) return;
      setSending(true);
      setError(null);
      const tempUserId = `tmp-u-${Date.now()}`;
      const tempAsstId = `tmp-a-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: tempUserId, role: "user", content: text, pending: true, created_at: new Date().toISOString() },
      ]);

      let acc = "";
      let streamFailed = false;
      try {
        await streamSSE(`/conversations/${conversationId}/messages/stream`, {
          body: { content: text },
          onEvent: (event, data) => {
            if (event === "meta") {
              setMessages((prev) => [
                ...prev.map((m) => (m.id === tempUserId ? { ...data.user_message } : m)),
                { id: tempAsstId, role: "assistant", content: "", pending: true, created_at: new Date().toISOString() },
              ]);
            } else if (event === "token") {
              acc += data.text || "";
              setMessages((prev) => prev.map((m) => (m.id === tempAsstId ? { ...m, content: acc } : m)));
            } else if (event === "done") {
              window.dispatchEvent(new Event("pf-quota-changed"));
              setMessages((prev) => prev.map((m) => (m.id === tempAsstId ? { ...data.assistant_message } : m)));
            } else if (event === "suggestions") {
              // 追问气泡挂到最后一条助手消息上；done 已把它的临时 id 换成库里真实 id，
              // 所以按 role 定位最后一条即可，不依赖 id。
              const questions = Array.isArray(data.questions) ? data.questions.slice(0, 3) : [];
              setMessages((prev) => {
                const idx = prev.map((m) => m.role).lastIndexOf("assistant");
                if (idx < 0) return prev;
                const next = [...prev];
                next[idx] = { ...next[idx], suggestions: questions };
                return next;
              });
            } else if (event === "error") {
              streamFailed = true;
              setError(data.message);
            }
          },
        });
      } catch (e) {
        streamFailed = true;
        setError(e.code === "QUOTA_EXCEEDED" ? "今日对话次数已用尽，明天再聊吧" : e.message);
      }

      // 失败清理：移除占位消息（后端 error 事件时已回滚用户消息）
      if (streamFailed) {
        setMessages((prev) => prev.filter((m) => m.id !== tempUserId && m.id !== tempAsstId));
      }
      setSending(false);
    },
    [conversationId, sending]
  );

  // 流式占位（内容还空的助手消息）不参与渲染：骨架的「正在写」指示已承担该状态，
  // 否则会出现一张空白气泡 + 一个打字指示同时存在
  const visible = messages.filter((m) => m.role !== "assistant" || (m.content || "").trim().length > 0);

  return { messages: visible, loading, sending, error, send, reload: () => load(conversationId) };
}
