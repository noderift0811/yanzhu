import { useEffect, useRef, useState } from "react";
import { Button, Dropdown, Segmented, Space, Tooltip, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import {
  AppstoreOutlined,
  ArrowLeftOutlined,
  BgColorsOutlined,
  BookOutlined,
  DownloadOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  PlusOutlined,
  ReloadOutlined,
  SkinOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { request } from "../lib/api.js";
import { useMe } from "../lib/me.js";
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
  ];
  const onSite = ({ key }) => {
    if (key === "create") setCreateOpen(true);
    else if (key === "personas") navigate("/personas");
    else if (key === "scene") navigate("/scene");
  };
  // 全屏沉浸：优先用浏览器全屏 API，被拒（iframe / 权限策略）时退化为 CSS 全屏覆盖
  const [immersive, setImmersive] = useState(false);
  const rootRef = useRef(null);
  // 配色草稿：面板里改动时先落到这里实时预览，取消就丢弃，保存后由后端数据接管
  const [draftTheme, setDraftTheme] = useState(null);
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

  return (
    <div
      ref={rootRef}
      className={`pf-chat ${className}${immersive ? " pf-chat--immersive" : ""}`}
      style={style}
    >
      <header className="pf-chat-header">
        <div className="pf-chat-title">
          {onBack && (
            <Tooltip title="返回">
              <Button size="small" type="text" icon={<ArrowLeftOutlined />} onClick={onBack} />
            </Tooltip>
          )}
          <Avatar name={spec.name} theme={activeTheme} size={40} />
          <div>
            <Typography.Text strong className="pf-chat-name">
              {spec.name || current?.name}
            </Typography.Text>
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
          <Button size="small" type="text" onClick={newConversation} icon={<PlusOutlined />}>
            新会话
          </Button>
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
          <Tooltip title={immersive ? "退出沉浸（Esc）" : "全屏沉浸，只留这个人格"}>
            <Button
              size="small"
              type="text"
              icon={immersive ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={toggleImmersive}
            />
          </Tooltip>
          {headerExtra}
        </Space>
      </header>

      {conversations.length > 1 && (
        <div className="pf-conv-bar">
          <Segmented
            value={cid}
            onChange={setCid}
            options={conversations.map((c) => ({
              value: c.id,
              label: <span className="pf-conv-label">{c.title}</span>,
            }))}
          />
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
    </div>
  );
}
