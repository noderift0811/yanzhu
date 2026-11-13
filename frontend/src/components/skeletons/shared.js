import { useState } from "react";

// 骨架共用工具。16 套骨架各写一份 submit 与时间格式必然漂移，统一收在这里。
// 约定：骨架只负责「消息区 + 输入区」的视觉人格，其余 chrome 由 ChatView 渲染。

export function hhmm(iso) {
  return (iso || "").slice(11, 16) || "--:--";
}

// 日期戳：2026.10.26 / 2026-10-26
export function ymd(iso, sep = ".") {
  const d = (iso || "").slice(0, 10);
  return d ? d.replaceAll("-", sep) : "";
}

// 任务时间码：T+14:02:33
export function missionClock(iso) {
  return `T+${(iso || "").slice(11, 19) || "00:00:00"}`;
}

// 首屏空态：没有任何消息且不在发送中
export function isOpening(messages, sending) {
  return messages.length === 0 && !sending;
}

// 打字指示只在「还没吐出第一个字」时出现，已开始流式由正文自身增长示意
export function isTyping(messages, sending) {
  return sending && messages[messages.length - 1]?.role !== "assistant";
}

// 草稿状态机：Enter 发送、Shift+Enter 换行、发送中锁定
export function useComposer(onSend, sending) {
  const [draft, setDraft] = useState("");
  const submit = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };
  const onEnter = (e) => {
    if (!e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };
  return { draft, setDraft, submit, onEnter };
}

// 稳定的单据编号：取 persona id 前 4 位，刷新不变
export function docNo(persona, fallback = "0000") {
  const raw = String(persona?.id || "").replace(/[^0-9a-zA-Z]/g, "");
  return (raw.slice(0, 4) || fallback).toUpperCase();
}
