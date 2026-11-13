// 「把搭好的网页带走」：把当前聊天页的 DOM 快照 + 用到的样式内联成单文件 HTML。
// 为什么不用另一套静态模板重新拼装：16 套骨架各有独立布局，重写一份必然与线上页面
// 走样；直接快照能保证「导出即所见」。代价是文件里带了一份按选择器裁剪过的 CSS。
import { personaLabel, safeFileName } from "./exportChat.js";

const MEDIA_RULE = 4;
const KEYFRAMES_RULE = 7;
const SUPPORTS_RULE = 12;

// 从 DOM 里收集所有出现过的 class：样式裁剪的唯一依据
function collectUsedClasses(root) {
  const used = new Set();
  const walk = (el) => {
    if (el.classList) el.classList.forEach((c) => used.add(c));
    if (el.id) used.add(`#${el.id}`);
  };
  walk(root);
  root.querySelectorAll("*").forEach(walk);
  return used;
}

function selectorKeeps(selector, used) {
  const classes = selector.match(/\.-?[_a-zA-Z][_a-zA-Z0-9-]*/g);
  // 纯标签/属性/伪类选择器（body、*、[hidden]）无法判断，保守保留
  if (!classes) return true;
  return classes.some((c) => used.has(c.slice(1)));
}

function harvestRules(rules, used, out) {
  for (const rule of rules) {
    // @keyframes 的 cssRules 是帧规则（没有 selectorText），必须在分组判断前拦下
    if (rule.type === KEYFRAMES_RULE) {
      out.push(rule.cssText);
      continue;
    }
    if (rule.cssRules && rule.cssRules.length && rule.conditionText) {
      const inner = [];
      harvestRules(rule.cssRules, used, inner);
      if (!inner.length) continue;
      const at = rule.type === SUPPORTS_RULE ? `@supports ${rule.conditionText}` : `@media ${rule.conditionText}`;
      if (rule.type === MEDIA_RULE || rule.type === SUPPORTS_RULE) {
        out.push(`${at} {\n${inner.join("\n")}\n}`);
        continue;
      }
      out.push(inner.join("\n"));
      continue;
    }
    if (rule.selectorText) {
      if (selectorKeeps(rule.selectorText, used)) out.push(rule.cssText);
      continue;
    }
    // @font-face / @property 等无法按选择器裁剪的规则，一律保留
    out.push(rule.cssText);
  }
}

// 合并文档里所有可读样式表（含 antd 运行时注入的 <style>），按选择器裁剪后返回文本
export function collectStyles(used) {
  const out = [];
  const seen = new Set();
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // 跨域样式表读不到 cssRules，跳过（本项目无外链样式，正常不会命中）
    }
    if (!rules || !rules.length) continue;
    const text = [];
    try {
      harvestRules(rules, used, text);
    } catch {
      continue;
    }
    for (const chunk of text) {
      if (seen.has(chunk)) continue;
      seen.add(chunk);
      out.push(chunk);
    }
  }
  return out.join("\n");
}

const EXPORT_CSS = (bg) => `
/* ---- 导出页补丁：脱离应用外壳独立成页 ---- */
html, body { margin: 0; padding: 0; background: ${bg}; }
.pf-home { padding-top: 24px; padding-bottom: 24px; }
.pf-chat { min-height: calc(100vh - 118px); }
.pf-export-note {
  max-width: 1080px;
  margin: 4px auto 20px;
  padding: 0 20px;
  font: 12px/1.6 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  opacity: 0.45;
  text-align: center;
}
`;

function esc(text) {
  return String(text || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

/**
 * 生成单文件 HTML 字符串。
 * @param {HTMLElement} rootEl 当前 .pf-chat 容器
 * @param {object} persona 人格详情（含 spec / keywords）
 * @param {object} conversation 当前会话
 */
export function buildPageHtml({ rootEl, persona, conversation, exportedAt = new Date() }) {
  if (!rootEl) throw new Error("页面还没准备好，稍后再试");

  const clone = rootEl.cloneNode(true);
  clone.classList.remove("pf-chat--immersive");

  // 头部按钮组与会话切换条在静态页里点不动，留着只会误导，直接摘掉
  clone.querySelectorAll(".pf-chat-header .ant-space, .pf-conv-bar").forEach((n) => n.remove());
  // 输入区降级为示意：antd 的 Input 用属性设值，TextArea 用文本节点，两处都要清
  clone.querySelectorAll("textarea, input").forEach((el) => {
    el.setAttribute("placeholder", "这是导出的静态页面，不会回应消息");
    el.setAttribute("readonly", "readonly");
    if (el.tagName === "TEXTAREA") el.textContent = "";
    else {
      el.setAttribute("value", "");
      el.value = "";
    }
  });
  clone.querySelectorAll("button").forEach((el) => el.setAttribute("disabled", "disabled"));
  // 流式期间的动画残留（打字点）不必带走
  clone.querySelectorAll(".sk-typing").forEach((n) => n.remove());

  const used = collectUsedClasses(clone);
  const css = collectStyles(used);
  const spec = persona?.spec || {};
  // 页面底色直接用主题值：导出的 body 上没有 --pf-bg 变量，靠变量会退化成浅灰
  const pageBg = spec.theme?.bg || "#f6f7fb";
  const title = `${spec.name || persona?.name || "人格"} · ${spec.page_copy?.title || "对话"}`;
  const exported = exportedAt.toISOString();
  const humanTime = exported.slice(0, 16).replace("T", " ");
  // 配置随页面一起走：想改配色/骨架/人设提示词，直接读这段 JSON
  const specJson = JSON.stringify(
    {
      exported_at: exported,
      persona: {
        id: persona?.id,
        name: spec.name || persona?.name,
        skeleton_id: spec.skeleton_id,
        page_copy: spec.page_copy,
        theme: spec.theme,
        system_prompt: spec.system_prompt,
        opening_message: spec.opening_message,
        keywords: persona?.keywords,
      },
      conversation: { id: conversation?.id, title: conversation?.title },
    },
    null,
    2
  ).replace(/</g, "\\u003c");

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="generator" content="YanZhu" />
<title>${esc(title)}</title>
<!-- 言筑 YanZhu 导出 · ${esc(spec.skeleton_id || "")} · ${humanTime} · 静态页面，无需任何依赖 -->
<style>
${css}
${EXPORT_CSS(pageBg)}
</style>
</head>
<body style="background:${pageBg}">
<div class="pf-home">
${clone.outerHTML}
</div>
<footer class="pf-export-note">言筑 YanZhu · 导出于 ${humanTime} · 这是一张静态页面，对话记录止于导出时刻</footer>
<script type="application/json" id="yanzhu-spec">
${specJson}
</script>
</body>
</html>
`;
}

export function pageFileName(persona, exportedAt = new Date()) {
  const name = personaLabel(persona);
  const d = exportedAt;
  const pad = (n) => String(n).padStart(2, "0");
  const stamp = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
  return `${safeFileName(`言筑-${name}-页面-${stamp}`, "言筑-页面")}.html`;
}

export function downloadHtml(filename, html) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
