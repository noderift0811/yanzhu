import { useEffect, useRef, useState } from "react";
import { Button, Dropdown, Popconfirm, Space, Tooltip, message } from "antd";
import { useNavigate } from "react-router-dom";
import {
  AppstoreOutlined,
  ArrowLeftOutlined,
  BgColorsOutlined,
  BookOutlined,
  CloseOutlined,
  DownloadOutlined,
  FileTextOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  LogoutOutlined,
  PlusOutlined,
  ReloadOutlined,
  SkinOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { authStore, request } from "../lib/api.js";
import { resetMe, useMe } from "../lib/me.js";
import { registerDecoration } from "../lib/decoration.js";
import { useChat } from "../hooks/useChat.js";
import { useThemeVars } from "../hooks/useThemeVars.js";
import {
  buildConversationJson,
  buildConversationMarkdown,
  buildConversationText,
  conversationFileBase,
  downloadText,
  personaLabel,
} from "../lib/exportChat.js";
import { buildPageHtml, downloadHtml, pageFileName } from "../lib/exportPage.js";
import { getSkeleton, SKELETON_NAMES } from "./skeletons/index.js";
import Avatar from "./Avatar.jsx";
import AvatarEditor from "./AvatarEditor.jsx";
import PersonaSettingsModal from "./PersonaSettingsModal.jsx";
import SkeletonPicker from "./SkeletonPicker.jsx";
import ThemePanel from "./ThemePanel.jsx";
import PersonaBriefModal from "./PersonaBriefModal.jsx";

const SAVE_ITEMS = [
  { key: "md", label: "对话存为 Markdown" },
  { key: "txt", label: "对话存为纯文本" },
  { key: "json", label: "对话存为 JSON（备份）" },
  { type: "divider" },
  { key: "html", label: "网页存为单文件 HTML" },
  { key: "spec", label: "配置存为 JSON" },
];

// 外观菜单：换骨架与调配色同属「视觉调整」，收进一个入口减少头部噪音
const LOOK_ITEMS = [
  { key: "skeleton", icon: <SwapOutlined />, label: "换一套风格（骨架）" },
  { key: "theme", icon: <BgColorsOutlined />, label: "调整配色" },
];

// 与后端 scenes.tone_clause 保持一致：导出提示词时把当前账号的语气开关一并带上。
function toneClause(tone) {
  const bits = [];
  if (tone?.calm) bits.push("语气更沉稳：先承接再回应，不急着给方案");
  if (tone?.brief) bits.push("回复更简短：控制在三句以内，能一句说完就不写第二句");
  if (tone?.no_exclaim) bits.push("不使用感叹号，也不用「呢 / 哦 / 呀」这类语气词");
  return bits.length ? "【本次对话的语气偏好】" + bits.join("；") + "。这条只影响说法，不改变身份与边界。" : "";
}

// 聊天视图：共用 chrome（头部 + 会话切换）+ 骨架组件（视觉人格）
export default function ChatView({ persona, onBack, headerExtra, onPersonaChange }) {
  const navigate = useNavigate();
  // 换骨架就地生效：不动会话、不重放建造、不重载消息
  const [current, setCurrent] = useState(persona);
  const [pickOpen, setPickOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  // 重建：改限定词后重跑五步链路（覆盖当前 / 另建），入口在头部
  const [rebuildOpen, setRebuildOpen] = useState(false);
  // 新建：站点下拉里直接打开轻弹窗（与重建共用 PersonaBriefModal）
  const [createOpen, setCreateOpen] = useState(false);
  // 人格设置：点头像旁的名字进入，只做头像 / 名字 / 补充设定的确定性修改
  const [settingsOpen, setSettingsOpen] = useState(false);
  const goBuild = ({ body, preset }) => navigate("/build", { state: { body, preset } });
  // 站点下拉：全局导航（新建 / 人格库 / 换场景）+ 今日配额展示
  const me = useMe();
  const genLeft = me ? me.quota_gen_daily - me.quota_gen_used : null;
  const chatLeft = me ? me.quota_chat_daily - me.quota_chat_used : null;
  const siteItems = [
    { key: "create", icon: <PlusOutlined />, label: "新建人格" },
    { key: "personas", icon: <BookOutlined />, label: "人格库" },
    { key: "scene", icon: <SwapOutlined />, label: "换场景" },
    { type: "divider" },
    {
      key: "quota",
      disabled: true,
      label: (
        <span className="pf-quota-menu">
          今日配额 · 生成 {genLeft ?? "…"} · 对话 {chatLeft ?? "…"}
        </span>
      ),
    },
    { type: "divider" },
    { key: "logout", icon: <LogoutOutlined />, label: "退出登录" },
  ];
  const logout = () => {
    authStore.clear();
    resetMe(); // 不清缓存的话，换账号进来会先闪一下上一个人的场景
    location.hash = "#/login";
  };
  const onSite = ({ key }) => {
    if (key === "create") setCreateOpen(true);
    else if (key === "personas") navigate("/personas");
    else if (key === "scene") navigate("/scene");
    else if (key === "logout") logout();
  };
  // 全屏沉浸：优先用浏览器全屏 API，被拒（iframe / 权限策略）时退化为 CSS 全屏覆盖
  const [immersive, setImmersive] = useState(false);
  // 沉浸引导悬浮框：关闭后写入 localStorage，不再反复打扰；进入沉浸时自动隐藏。
  const [immHintClosed, setImmHintClosed] = useState(() => {
    try { return localStorage.getItem("yz-immersive-hint-closed") === "1"; } catch { return false; }
  });
  const closeImmHint = () => {
    setImmHintClosed(true);
    try { localStorage.setItem("yz-immersive-hint-closed", "1"); } catch { /* 隐私模式下忽略 */ }
  };
  const rootRef = useRef(null);
  // 配色草稿：面板里改动时先落到这里实时预览，取消就丢弃，保存后由后端数据接管
  const [draftTheme, setDraftTheme] = useState(null);
  // 装修台桥接：把聊天页持有的面板打开函数 + 预览/保存通道登记给全局悬浮球。
  // 面板本体仍在这里渲染，预览/保存逻辑原样复用，悬浮球只是多一个就地入口。
  // AI 装修也走这条通道：先 previewTheme 实时预览，用户点「采用」才 applyTheme 落库。
  // 用 ref 承载最新值，登记只做一次，避免每次改配色都重注册。
  const decorationRef = useRef(null);
  decorationRef.current = {
    persona: current,
    skeletonName: current?.skeleton_name || current?.skeleton_id || "",
    openTheme: () => setThemeOpen(true),
    openSkeleton: () => setPickOpen(true),
    previewTheme: (theme) => setDraftTheme(theme),
    resetPreview: () => setDraftTheme(null),
    applyTheme: async (theme) => {
      const updated = await request(`/personas/${current.id}`, {
        method: "PATCH", body: { theme },
      });
      setDraftTheme(null);
      setCurrent(updated);
      return updated;
    },
  };
  useEffect(() => {
    const unregister = registerDecoration({
      get persona() { return decorationRef.current.persona; },
      get skeletonName() { return decorationRef.current.skeletonName; },
      openTheme: () => decorationRef.current.openTheme(),
      openSkeleton: () => decorationRef.current.openSkeleton(),
      previewTheme: (theme) => decorationRef.current.previewTheme(theme),
      resetPreview: () => decorationRef.current.resetPreview(),
      applyTheme: (theme) => decorationRef.current.applyTheme(theme),
    });
    return unregister;
  }, []);
  useEffect(() => {
    setCurrent(persona);
  }, [persona]);

  useEffect(() => {
    document.body.classList.toggle("pf-immersive", immersive);
    return () => document.body.classList.remove("pf-immersive");
  }, [immersive]);

  useEffect(() => {
    // 浏览器全屏被 Esc 或系统手势退出时，状态要跟着回来，否则只剩一层假全屏
    const onFullscreenChange = () => {
      if (!document.fullscreenElement) setImmersive(false);
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") setImmersive((v) => (v ? false : v));
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const spec = current?.spec || {};
  const avatarState = current?.avatar || spec.avatar || { mode: "auto" };
  const hiddenAvatar = avatarState.mode === "hidden";
  const activeTheme = draftTheme || spec.theme;
  const activeSpec = draftTheme ? { ...spec, theme: draftTheme } : spec;
  const activePersona = draftTheme ? { ...current, spec: activeSpec } : current;
  const { style, className } = useThemeVars(activeTheme);
  const Skeleton = getSkeleton(spec.skeleton_id);

  const [conversations, setConversations] = useState([]);
  const [cid, setCid] = useState(null);
  const [convLoading, setConvLoading] = useState(true);
  const chat = useChat({ conversationId: cid });

  useEffect(() => {
    let live = true;
    (async () => {
      setConvLoading(true);
      try {
        const data = await request(`/personas/${persona.id}/conversations`);
        const items = data.items || [];
        if (!live) return;
        setConversations(items);
        if (items.length) {
          setCid(items[0].id);
          return;
        }
        // 无会话则自动创建（种子开场白与建造揭晓一致）
        const created = await request(`/personas/${persona.id}/conversations`, { method: "POST", body: {} });
        if (!live) return;
        setConversations([created]);
        setCid(created.id);
      } catch (e) {
        if (live) message.error(e.message);
      } finally {
        if (live) setConvLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [persona.id]);

  const newConversation = async () => {
    try {
      const created = await request(`/personas/${persona.id}/conversations`, { method: "POST", body: {} });
      setConversations((prev) => [created, ...prev]);
      setCid(created.id);
    } catch (e) {
      message.error(e.message);
    }
  };

  // 关闭会话：删库后切到相邻会话；若这是最后一个，立刻补一个空会话，
  // 保证聊天框永远有落点（种子开场白与建造揭晓一致）。
  const closeConversation = async (target) => {
    try {
      await request(`/conversations/${target.id}`, { method: "DELETE" });
      let left = conversations.filter((c) => c.id !== target.id);
      if (target.id === cid) {
        if (!left.length) {
          const created = await request(`/personas/${persona.id}/conversations`, { method: "POST", body: {} });
          left = [created];
        }
        setCid(left[0].id);
      }
      setConversations(left);
      message.success("会话已关闭");
    } catch (e) {
      message.error(e.message);
    }
  };

  const toggleImmersive = async () => {
    if (!immersive) {
      setImmersive(true);
      try {
        // 关键：全屏的是整页（documentElement）而不是聊天容器。
        // 浏览器全屏只渲染全屏元素内部，而 antd 的菜单 / 弹窗都挂在 body 上——
        // 若只把 .pf-chat 全屏，"保存"菜单和"换风格"弹窗会看不见也点不到。
        // 视口占满交给 CSS（.pf-chat--immersive 的 fixed inset:0），视觉一致。
        await document.documentElement.requestFullscreen?.({ navigationUI: "hide" });
      } catch {
        /* 浏览器拒绝就靠 CSS 全屏兜住，功能不降级 */
      }
      return;
    }
    setImmersive(false);
    if (document.fullscreenElement) {
      try {
        await document.exitFullscreen();
      } catch {
        /* 已经退出，忽略 */
      }
    }
  };

  const conversation = conversations.find((c) => c.id === cid) || null;

  // 消息区改成内部滚动后，切换会话 / 流式吐字都要跟到底部。
  // 16 套骨架共用 .sk-msgs，这里只在聊天页容器里找一个节点，比改 16 个组件稳。
  const lastMessage = chat.messages[chat.messages.length - 1];
  const lastContentLength = (lastMessage?.content || "").length;
  useEffect(() => {
    const box = rootRef.current?.querySelector(".sk-msgs");
    if (box) box.scrollTop = box.scrollHeight;
  }, [cid, chat.messages.length, lastContentLength, chat.sending]);

  const save = (kind) => {
    const messages = chat.messages;
    if (!messages.length) {
      message.warning("这个会话还没有可保存的内容");
      return;
    }
    const now = new Date();
    const base = conversationFileBase(current, conversation, now);
    const payload = { persona: current, conversation, messages, exportedAt: now };
    try {
      if (kind === "md") {
        downloadText(`${base}.md`, buildConversationMarkdown(payload), "text/markdown;charset=utf-8");
      } else if (kind === "txt") {
        downloadText(`${base}.txt`, buildConversationText(payload));
      } else if (kind === "json") {
        downloadText(`${base}.json`, buildConversationJson(payload), "application/json;charset=utf-8");
      } else if (kind === "html") {
        const html = buildPageHtml({ ...payload, rootEl: rootRef.current });
        downloadHtml(pageFileName(current, now), html);
      } else if (kind === "spec") {
        const spec = {
          exported_at: now.toISOString(),
          name: personaLabel(current),
          brief: current?.brief || null,
          keywords: current?.keywords || null,
          ...(current?.spec || {}),
        };
        downloadText(`${base}-配置.json`, JSON.stringify(spec, null, 2), "application/json;charset=utf-8");
      } else {
        return;
      }
      message.success("已保存到浏览器的下载目录");
    } catch (e) {
      message.error(`保存失败：${e.message}`);
    }
  };

  // 导出当前人格真正会用到的全部提示词：生成期写入的 system_prompt、
  // 用户在设置页补的设定、账号级运行时语气指令，以及开场白。
  const exportPrompts = () => {
    const runtime = toneClause(me?.tone);
    const lines = [
      `# ${spec.name || current?.name} · 提示词导出`,
      "",
      `- 导出时间：${new Date().toLocaleString("zh-CN")}`,
      `- 场景：${current?.scene_id || me?.primary_scene || "自由创作"}`,
      `- 骨架：${SKELETON_NAMES[spec.skeleton_id] || spec.skeleton_id || "—"}`,
      "",
      "## 1. 人格系统提示词（生成期写入，对话时原样作为 system role）",
      "",
      "```text",
      spec.system_prompt || "（暂无）",
      "```",
      "",
      "## 2. 补充人格设定（设置页追加，确定性拼接，不重生成）",
      "",
      spec.extra_prompt || "（暂无）",
      "",
      "## 3. 运行时语气指令（当前账号开关，逐条对话追加，不落库）",
      "",
      runtime || "（未开启任何语气开关）",
      "",
      "## 4. 开场白",
      "",
      spec.opening_message || "（暂无）",
      "",
      "---",
      "由言筑 YanZhu 导出。语气开关只影响说法，不改变身份与边界。",
    ];
    const base = conversationFileBase(current, conversation, new Date());
    try {
      downloadText(`${base}-提示词.md`, lines.join("\n"), "text/markdown;charset=utf-8");
      message.success("提示词已导出到下载目录");
    } catch (e) {
      message.error(`导出失败：${e.message}`);
    }
  };

  return (
    <div
      ref={rootRef}
      className={`pf-chat ${className}${immersive ? " pf-chat--immersive" : ""}`}
      style={style}
    >
      <header className="pf-chat-header">
        <div className={`pf-chat-title${hiddenAvatar ? " pf-chat-title--no-avatar" : ""}`}>
          {onBack && (
            <Tooltip title="返回">
              <Button size="small" type="text" icon={<ArrowLeftOutlined />} onClick={onBack} />
            </Tooltip>
          )}
          {!hiddenAvatar && (
            <AvatarEditor
              persona={current}
              theme={activeTheme}
              avatar={avatarState}
              onChanged={(updated) => { setCurrent(updated); onPersonaChange?.(updated); }}
            >
              <Avatar
                name={spec.name}
                theme={activeTheme}
                size={40}
                avatar={avatarState}
                onEdit={() => {}}
              />
            </AvatarEditor>
          )}
          <div className="pf-chat-title-text">
            <Tooltip title="点头像/名字可设置头像、名字并补充人格设定">
              <button
                type="button"
                className="pf-chat-name-btn"
                onClick={() => setSettingsOpen(true)}
              >
                {spec.name || current?.name}
              </button>
            </Tooltip>
            <div className="pf-chat-sub">
              {spec.page_copy?.title} · {SKELETON_NAMES[spec.skeleton_id] || spec.skeleton_id}
              {current?.status === "needs_review" && <span className="pf-badge-warn">待重生成</span>}
            </div>
          </div>
        </div>
        <Space wrap size={4}>
          <Dropdown trigger={["click"]} menu={{ items: siteItems, onClick: onSite }}>
            <Button size="small" type="text" icon={<AppstoreOutlined />}>
              站点
            </Button>
          </Dropdown>
          <Tooltip title="改限定词，重跑五步 Agent 链路（覆盖当前或另建一个）">
            <Button size="small" type="text" icon={<ReloadOutlined />} onClick={() => setRebuildOpen(true)}>
              重建
            </Button>
          </Tooltip>
          <Dropdown
            trigger={["click"]}
            menu={{
              items: LOOK_ITEMS,
              onClick: ({ key }) => (key === "skeleton" ? setPickOpen(true) : setThemeOpen(true)),
            }}
          >
            <Button size="small" type="text" icon={<SkinOutlined />}>
              外观
            </Button>
          </Dropdown>
          <Dropdown
            trigger={["click"]}
            menu={{ items: SAVE_ITEMS, onClick: ({ key }) => save(key) }}
            disabled={!chat.messages.length}
          >
            <Button size="small" type="text" icon={<DownloadOutlined />}>
              保存
            </Button>
          </Dropdown>
          <Tooltip title="导出这个人格当前生效的全部提示词">
            <Button size="small" type="text" icon={<FileTextOutlined />} onClick={exportPrompts}>
              提示词
            </Button>
          </Tooltip>
          <Tooltip title={immersive ? "退出沉浸（Esc）" : "全屏沉浸，只留这个人格"}>
            <Button
              size="small"
              type="text"
              icon={immersive ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={toggleImmersive}
            >
              {immersive ? "退出沉浸" : "沉浸"}
            </Button>
          </Tooltip>
          {headerExtra}
        </Space>
      </header>

      {!immersive && !immHintClosed && (
        <div className="pf-imm-hint" role="note">
          <button className="pf-imm-hint-close" onClick={closeImmHint} aria-label="关闭沉浸提示">
            <CloseOutlined />
          </button>
          <div className="pf-imm-hint-icon"><FullscreenOutlined /></div>
          <div className="pf-imm-hint-body">
            <div className="pf-imm-hint-title">想专心聊聊？</div>
            <div className="pf-imm-hint-desc">进入沉浸模式，只留下这个页面，屏蔽一切打扰。</div>
            <button className="pf-imm-hint-cta" onClick={toggleImmersive}>进入沉浸 →</button>
          </div>
        </div>
      )}

      {conversations.length > 0 && (
        <div className="pf-conv-bar">
          <div className="pf-conv-tabs" role="tablist" aria-label="会话列表">
            {conversations.map((c) => (
              <div
                key={c.id}
                role="tab"
                aria-selected={c.id === cid}
                className={`pf-conv-tab${c.id === cid ? " is-active" : ""}`}
              >
                <button className="pf-conv-tab-main" onClick={() => setCid(c.id)}>
                  <span className="pf-conv-label">{c.title}</span>
                </button>
                <Popconfirm
                  title="关闭这个会话？"
                  description="其中的对话内容会被删除"
                  okText="关闭"
                  cancelText="取消"
                  onConfirm={() => closeConversation(c)}
                >
                  <button
                    className="pf-conv-tab-close"
                    aria-label={`关闭会话：${c.title}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <CloseOutlined />
                  </button>
                </Popconfirm>
              </div>
            ))}
            <Tooltip title="新会话">
              <button className="pf-conv-tab-add" aria-label="新会话" onClick={newConversation}>
                <PlusOutlined />
              </button>
            </Tooltip>
          </div>
        </div>
      )}

      {convLoading ? (
        <div className="pf-chat-loading">正在加载会话…</div>
      ) : (
        <Skeleton
          persona={activePersona}
          messages={chat.messages}
          sending={chat.sending}
          error={chat.error}
          onSend={chat.send}
        />
      )}

      <SkeletonPicker
        open={pickOpen}
        persona={current}
        onClose={() => setPickOpen(false)}
        onSwitched={(updated) => {
          setCurrent(updated);
          onPersonaChange?.(updated); // 同步给外层，避免「重看建造」回来又变回旧骨架
          setPickOpen(false);
        }}
      />

      <ThemePanel
        open={themeOpen}
        persona={current}
        onPreview={setDraftTheme}
        onClose={() => setThemeOpen(false)}
        onSaved={(updated) => {
          setCurrent(updated);
          onPersonaChange?.(updated);
          setThemeOpen(false);
        }}
      />

      <PersonaBriefModal
        open={rebuildOpen}
        mode="rebuild"
        initial={{
          tags: current?.keywords?.tags || [],
          free_text: current?.keywords?.free_text || "",
          name: current?.name || "",
        }}
        rebuildTargetId={current?.id}
        rebuildName={current?.name}
        onCancel={() => setRebuildOpen(false)}
        onConfirm={goBuild}
      />

      <PersonaBriefModal
        open={createOpen}
        mode="create"
        onCancel={() => setCreateOpen(false)}
        onConfirm={goBuild}
      />

      <PersonaSettingsModal
        open={settingsOpen}
        persona={current}
        theme={activeTheme}
        onCancel={() => setSettingsOpen(false)}
        onSaved={(updated) => {
          setCurrent(updated);
          onPersonaChange?.(updated);
          setSettingsOpen(false);
        }}
      />
    </div>
  );
}
