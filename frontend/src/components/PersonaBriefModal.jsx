import { useEffect, useState } from "react";
import { Input, Modal, Radio, Tag, Typography, message } from "antd";
import { request } from "../lib/api.js";
import { useMe } from "../lib/me.js";
import TagEditor from "./TagEditor.jsx";
import NameField from "./NameField.jsx";

const EMPTY = { tags: [], free_text: "", name: "" };

// 新建 / 重建共用的轻弹窗：标签 + 描述 + 名字 +（场景）演示输入。
// 提交后由调用方跳 /build 看五步施工直播——弹窗只收输入，不塞施工过程，
// 因为五步时间线需要整个舞台，塞进弹窗会挤（移动端尤其）。
// 布局约定：操作按钮走 Modal footer（固定可见，不随长内容被顶出可视区），
// 重建的「覆盖/另建」单选提前到说明文字后，先做决定再改限定词。
export default function PersonaBriefModal({
  open,
  mode = "create", // create | rebuild
  initial = EMPTY,
  rebuildTargetId = null,
  rebuildName = "",
  onCancel,
  onConfirm, // ({ body, preset }) => void
}) {
  const me = useMe();
  const [preset, setPreset] = useState(null);
  const [brief, setBrief] = useState(EMPTY);
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState("new"); // overwrite | new

  // 打开时重置草稿 + 按账号场景拉预设。initial 只在重建时带预填。
  useEffect(() => {
    if (!open) return;
    setBrief({
      tags: initial?.tags || [],
      free_text: initial?.free_text || "",
      name: initial?.name || "",
    });
    setQuery("");
    setTarget("new");
    if (me?.scene_id) {
      request("/meta/presets", { auth: false })
        .then((d) => {
          const p = (d.items || []).find((x) => x.id === me.scene_id);
          setPreset(p && p.id !== "free" ? p : null);
        })
        .catch(() => setPreset(null));
    } else {
      setPreset(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, me?.scene_id]);

  const valid = brief.tags.length > 0 || brief.free_text.trim().length > 0;

  const submit = () => {
    if (!valid) {
      message.warning("请至少选择一个标签或填写描述");
      return;
    }
    onConfirm({
      body: {
        tags: brief.tags,
        free_text: brief.free_text,
        name: (brief.name || "").trim() || undefined,
        user_query: preset ? query.trim() || preset.sample_prompt || "" : "",
        preset_id: preset ? preset.id : undefined,
        target_persona_id:
          mode === "rebuild" && target === "overwrite" ? rebuildTargetId : null,
      },
      preset,
    });
  };

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      width={720}
      className="pf-brief-modal"
      title={
        mode === "rebuild"
          ? `重建「${rebuildName || "这个人格"}」`
          : "新建人格"
      }
      okText={mode === "rebuild" ? "启动重建" : "开始生成"}
      okButtonProps={{ disabled: !valid }}
      onOk={submit}
      cancelText="取消"
      destroyOnClose
    >
      {preset && (
        <div className="pf-scene-banner">
          <div className="pf-scene-banner-main">
            <span className="pf-scene-banner-label">当前场景</span>
            <span className="pf-scene-banner-name">{me?.scene_name || preset.name}</span>
            {preset.subtitle && <span className="pf-scene-banner-sub">{preset.subtitle}</span>}
            <Tag className="yz-tag-brand">检索语料 · 安全边界 · 默认骨架都按它来</Tag>
          </div>
        </div>
      )}

      <Typography.Paragraph type="secondary" className="pf-brief-hint">
        {mode === "rebuild"
          ? "改限定词后重跑五步链路，页面会重新搭建；已有会话与消息不受影响。"
          : "点选贴合你想象的标签，至少选一个；也可以先在描述里写两句。"}
      </Typography.Paragraph>

      {mode === "rebuild" && (
        <div className="pf-rebuild-mode">
          <Radio.Group value={target} onChange={(e) => setTarget(e.target.value)}>
            <Radio value="overwrite">重做这个人格（覆盖当前页面）</Radio>
            <Radio value="new">另建一个（保留当前，新生成）</Radio>
          </Radio.Group>
        </div>
      )}

      <TagEditor value={brief} onChange={setBrief} />

      <NameField value={brief.name} onChange={(name) => setBrief((b) => ({ ...b, name }))} />

      {preset && (
        <div className="ag-query">
          <Typography.Text strong>演示输入（会先经过检索与安全护栏）</Typography.Text>
          <Typography.Paragraph type="secondary" className="ag-query-hint">
            现场改成任意表达即可验证护栏；它只影响本次检索与护栏，不写进人格。
          </Typography.Paragraph>
          <Input.TextArea
            rows={2}
            maxLength={200}
            showCount
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="写一句这个场景下用户可能说的话…"
          />
        </div>
      )}
    </Modal>
  );
}
