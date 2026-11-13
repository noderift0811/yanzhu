// 对话保存：Markdown / 纯文本 / JSON 三种格式，纯前端生成，不经后端、不耗配额。
// 设计取向：Markdown 给人读（粘进笔记就能看），JSON 给机器读（完整还原消息与时间）。

function pad(n) {
  return String(n).padStart(2, "0");
}

function humanTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso || "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function stamp(date) {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}`;
}

// 文件名安全化：Windows 不允许 \ / : * ? " < > |
export function safeFileName(input, fallback = "导出") {
  const cleaned = String(input || "")
    .replace(/[\\/:*?"<>|\r\n\t]/g, "_")
    .trim()
    .slice(0, 60);
  return cleaned || fallback;
}

export function personaLabel(persona) {
  return persona?.spec?.name || persona?.name || "人格";
}

function roleLabel(role, persona) {
  return role === "assistant" ? personaLabel(persona) : "我";
}

export function buildConversationMarkdown({ persona, conversation, messages, exportedAt = new Date() }) {
  const name = personaLabel(persona);
  const skeleton = persona?.spec?.page_copy?.title || persona?.skeleton_name || "";
  const lines = [
    `# 与「${name}」的对话`,
    "",
    `- 人格：${name}`,
    `- 页面：${skeleton}${persona?.skeleton_name ? ` · ${persona.skeleton_name}` : ""}`,
    `- 会话：${conversation?.title || "新会话"}`,
    `- 导出时间：${humanTime(exportedAt.toISOString())}`,
    `- 消息数：${messages.length}`,
    "",
    "---",
    "",
  ];
  messages.forEach((m) => {
    lines.push(`**${roleLabel(m.role, persona)}**（${humanTime(m.created_at)}）`);
    lines.push("");
    lines.push(m.content || "");
    lines.push("");
  });
  lines.push("---");
  lines.push("");
  lines.push("由言筑 YanZhu 导出");
  return lines.join("\n");
}

export function buildConversationText({ persona, conversation, messages, exportedAt = new Date() }) {
  const name = personaLabel(persona);
  const lines = [
    `与「${name}」的对话`,
    `会话：${conversation?.title || "新会话"}　消息数：${messages.length}　导出：${humanTime(exportedAt.toISOString())}`,
    "".padEnd(40, "="),
    "",
  ];
  messages.forEach((m) => {
    lines.push(`[${humanTime(m.created_at)}] ${roleLabel(m.role, persona)}：`);
    lines.push(m.content || "");
    lines.push("");
  });
  return lines.join("\n");
}

export function buildConversationJson({ persona, conversation, messages, exportedAt = new Date() }) {
  return JSON.stringify(
    {
      exported_at: exportedAt.toISOString(),
      exporter: "yanzhu",
      persona: {
        id: persona?.id,
        name: personaLabel(persona),
        skeleton_id: persona?.spec?.skeleton_id || persona?.skeleton_id,
        skeleton_name: persona?.skeleton_name,
        theme: persona?.spec?.theme || persona?.theme,
        page_copy: persona?.spec?.page_copy,
        system_prompt: persona?.spec?.system_prompt,
      },
      conversation: {
        id: conversation?.id,
        title: conversation?.title,
        created_at: conversation?.created_at,
        updated_at: conversation?.updated_at,
      },
      messages: messages.map((m) => ({
        role: m.role,
        content: m.content,
        created_at: m.created_at,
        tokens: m.tokens ?? null,
      })),
    },
    null,
    2
  );
}

export function conversationFileBase(persona, conversation, exportedAt = new Date()) {
  return safeFileName(
    `言筑-${personaLabel(persona)}-${conversation?.title || "会话"}-${stamp(exportedAt)}`,
    "言筑-导出"
  );
}

// 触发一次本地下载。Blob + a[download]，不依赖任何服务端接口。
export function downloadText(filename, text, mime = "text/plain;charset=utf-8") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
