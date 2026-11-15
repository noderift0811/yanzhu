import { useCallback, useEffect, useState } from "react";
import { Button, Card, Col, Empty, Modal, Popconfirm, Row, Space, Typography, message } from "antd";
import { BgColorsOutlined, EditOutlined, ReloadOutlined, SwapOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { request } from "../lib/api.js";
import AppHeader from "../components/AppHeader.jsx";
import TagEditor from "../components/TagEditor.jsx";
import NameField from "../components/NameField.jsx";
import Avatar from "../components/Avatar.jsx";
import SkeletonPicker from "../components/SkeletonPicker.jsx";
import ThemePanel from "../components/ThemePanel.jsx";
import PersonaPreview from "../components/PersonaPreview.jsx";
import { SKELETON_NAMES } from "../components/skeletons/index.js";

// 人格库：卡片网格 + 进入 / 改名 / 换骨架 / 重新生成 / 删除
export default function PersonasPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [regenTarget, setRegenTarget] = useState(null); // { persona, draft }
  const [regenLoading, setRegenLoading] = useState(false);
  const [pickTarget, setPickTarget] = useState(null); // 换骨架目标人格
  const [themeTarget, setThemeTarget] = useState(null); // 调配色目标人格
  const [renameTarget, setRenameTarget] = useState(null); // 改名目标人格
  const [renameValue, setRenameValue] = useState("");
  const [renaming, setRenaming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await request("/personas");
      setItems(data.items || []);
    } catch (e) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async (id) => {
    try {
      await request(`/personas/${id}`, { method: "DELETE" });
      message.success("已删除");
      load();
    } catch (e) {
      message.error(e.message);
    }
  };

  const regenerate = async () => {
    if (!regenTarget) return;
    const { persona, draft } = regenTarget;
    if (draft.tags.length === 0 && !draft.free_text.trim()) {
      message.warning("请至少选择一个标签或填写描述");
      return;
    }
    setRegenLoading(true);
    try {
      await request(`/personas/${persona.id}/regenerate`, {
        method: "POST",
        body: { tags: draft.tags, free_text: draft.free_text, name: (draft.name || "").trim() || undefined },
      });
      setRegenTarget(null);
      navigate(`/chat/${persona.id}`); // 进入即重放建造揭晓
    } catch (e) {
      message.error(e.message);
    } finally {
      setRegenLoading(false);
    }
  };

  const openRename = (p) => {
    setRenameTarget(p);
    setRenameValue(p.name || "");
  };

  const rename = async () => {
    const next = renameValue.trim();
    if (!next) {
      message.warning("名字不能为空");
      return;
    }
    if (next === renameTarget?.name) {
      setRenameTarget(null);
      return;
    }
    setRenaming(true);
    try {
      const updated = await request(`/personas/${renameTarget.id}`, {
        method: "PATCH",
        body: { name: next },
      });
      // 后端连 spec.name 与人设提示词一起改了，这里直接用返回值覆盖，避免本地状态落后
      setItems((prev) => prev.map((x) => (x.id === updated.id ? { ...x, ...updated } : x)));
      setRenameTarget(null);
      message.success("名字已更新");
    } catch (e) {
      message.error(e.message);
    } finally {
      setRenaming(false);
    }
  };

  return (
    <div className="pf-home">
      <AppHeader right={<Button size="small" type="text" onClick={() => navigate("/")}>新建人格</Button>} />
      <div className="pf-page">
        <Typography.Title level={4}>人格库</Typography.Title>
        {loading ? (
          <div className="pf-chat-loading">正在加载…</div>
        ) : items.length === 0 ? (
          <Empty description="还没有人格，去创建一个吧">
            <Button type="primary" onClick={() => navigate("/")}>
              新建人格
            </Button>
          </Empty>
        ) : (
          <Row gutter={[16, 16]} align="stretch">
            {items.map((p) => (
              <Col key={p.id} xs={24} sm={12} md={8}>
                <Card
                  className="pf-persona-card"
                  /* 封面即这套骨架的实时渲染：一眼看到界面长什么样，而不是读一行字 */
                  cover={<PersonaPreview persona={p} />}
                  actions={[
                    <Button key="open" type="link" size="small" onClick={() => navigate(`/chat/${p.id}`)}>
                      进入聊天
                    </Button>,
                    <Button key="rename" type="link" size="small" icon={<EditOutlined />} onClick={() => openRename(p)}>
                      改名
                    </Button>,
                    <Button
                      key="regen"
                      type="link"
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() =>
                        setRegenTarget({
                          persona: p,
                          draft: {
                            tags: p.keywords?.tags || [],
                            free_text: p.keywords?.free_text || "",
                            // 回填当前名字：重新生成不该悄悄把用户起的名字换掉
                            name: p.name || "",
                          },
                        })
                      }
                    >
                      重新生成
                    </Button>,
                    <Popconfirm
                      key="del"
                      title="删除这个人格？"
                      description="其会话与消息将一并删除"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => remove(p.id)}
                    >
                      <Button type="link" size="small" danger>
                        删除
                      </Button>
                    </Popconfirm>,
                  ]}
                >
                  <div className="pf-persona-head">
                    <Avatar name={p.name} theme={p.theme} size={48} />
                    <div>
                      <Typography.Text strong>{p.name}</Typography.Text>
                      <div className="pf-persona-sub">
                        <button
                          type="button"
                          className="pf-skeleton-chip"
                          onClick={() => setPickTarget(p)}
                          title="点一下换一套骨架，不消耗生成次数"
                        >
                          {SKELETON_NAMES[p.skeleton_id] || p.skeleton_id}
                          <SwapOutlined className="pf-skeleton-chip-dot" />
                        </button>
                        <button
                          type="button"
                          className="pf-theme-chip"
                          onClick={() => setThemeTarget(p)}
                          title="调整配色，不消耗生成次数"
                          aria-label="调整配色"
                        >
                          <BgColorsOutlined />
                        </button>
                        {p.status === "needs_review" && <span className="pf-badge-warn">待重生成</span>}
                      </div>
                    </div>
                  </div>
                  <Space wrap className="pf-persona-tags">
                    {(p.keywords?.tags || []).map((t) => (
                      <span key={t} className="pf-tag pf-tag-sm">
                        {t}
                      </span>
                    ))}
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>

      <Modal
        title="重新生成人格"
        open={!!regenTarget}
        onOk={regenerate}
        onCancel={() => setRegenTarget(null)}
        confirmLoading={regenLoading}
        okText="重新生成"
      >
        {regenTarget && (
          <>
            <Typography.Paragraph type="secondary">
              修改限定词后，工程师 AI 将重新生成人设与页面规格，并重放建造揭晓。
            </Typography.Paragraph>
            <NameField
              value={regenTarget.draft.name}
              label="角色名字"
              hint="已填的是当前名字；清空则让工程师 AI 重新起名"
              onChange={(name) => setRegenTarget({ ...regenTarget, draft: { ...regenTarget.draft, name } })}
            />
            <TagEditor
              value={regenTarget.draft}
              onChange={(draft) => setRegenTarget({ ...regenTarget, draft })}
            />
          </>
        )}
      </Modal>

      <Modal
        title="改个名字"
        open={!!renameTarget}
        onOk={rename}
        onCancel={() => setRenameTarget(null)}
        confirmLoading={renaming}
        okText="保存"
        okButtonProps={{ disabled: !renameValue.trim() }}
      >
        <Typography.Paragraph type="secondary">
          名字会同步写进人设提示词，聊天里的自称也会跟着变；已有会话与消息不受影响。
        </Typography.Paragraph>
        <NameField
          value={renameValue}
          label="角色名字"
          hint="2-20 字，随时可以再改"
          onChange={setRenameValue}
        />
      </Modal>

      <SkeletonPicker
        open={!!pickTarget}
        persona={pickTarget}
        onClose={() => setPickTarget(null)}
        onSwitched={(updated) => {
          setItems((prev) => prev.map((x) => (x.id === updated.id ? { ...x, ...updated } : x)));
          setPickTarget(null);
        }}
      />

      <ThemePanel
        open={!!themeTarget}
        persona={themeTarget}
        onClose={() => setThemeTarget(null)}
        onSaved={(updated) => {
          setItems((prev) => prev.map((x) => (x.id === updated.id ? { ...x, ...updated } : x)));
          setThemeTarget(null);
        }}
      />
    </div>
  );
}
