import { useEffect, useRef, useState } from "react";
import { Button, Input, Modal, Typography, message } from "antd";
import { CameraOutlined, CheckOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import { request } from "../lib/api.js";
import { compressImage } from "../lib/avatar.js";
import Avatar from "./Avatar.jsx";
import "../styles/persona-settings.css";

// 人格设置：点头像旁的名字进入。这里只做「不重生成」的本地增量定制——
// 头像三态、名字、补充人格设定（确定性追加进 system_prompt）。
// 真正重写人设仍走「重建」五步链路，两者入口刻意分开，避免用户误耗配额。
export default function PersonaSettingsModal({ open, persona, theme, onCancel, onSaved }) {
  const [name, setName] = useState("");
  const [extra, setExtra] = useState("");
  const [avatar, setAvatar] = useState({ mode: "auto", image: null });
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!open || !persona) return;
    const spec = persona.spec || {};
    setName(persona.name || spec.name || "");
    setExtra(spec.extra_prompt || "");
    setAvatar(persona.avatar || spec.avatar || { mode: "auto", image: null });
  }, [open, persona]);

  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setAvatar({ mode: "image", image: await compressImage(file) });
    } catch (err) {
      message.error(err.message || "图片处理失败");
    }
  };

  const save = async () => {
    const cleanName = name.trim();
    if (!cleanName) {
      message.warning("给这个人格起个名字吧");
      return;
    }
    setSaving(true);
    try {
      const updated = await request(`/personas/${persona.id}`, {
        method: "PATCH",
        body: { name: cleanName, avatar, extra_prompt: extra.trim() },
      });
      message.success("已保存，不消耗生成次数");
      onSaved?.(updated);
    } catch (e) {
      message.error(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const opt = (mode, icon, label, hint, onClick) => (
    <button
      type="button"
      className={`pf-set-opt${avatar.mode === mode ? " is-on" : ""}`}
      onClick={onClick}
      disabled={saving}
    >
      <span className="pf-set-opt-icon">{icon}</span>
      <span className="pf-set-opt-label">{label}<small>{hint}</small></span>
      {avatar.mode === mode && <CheckOutlined className="pf-set-opt-check" />}
    </button>
  );

  return (
    <Modal
      title="人格设置"
      open={open}
      onCancel={onCancel}
      width={520}
      maskClosable={!saving}
      footer={
        <div className="pf-set-footer">
          <Button onClick={onCancel} disabled={saving}>取消</Button>
          <Button type="primary" loading={saving} onClick={save}>保存设置</Button>
        </div>
      }
    >
      <div className="pf-set-body">
        <div className="pf-set-section-title">头像</div>
        <div className="pf-set-opts">
          {opt("auto", <Avatar name={name} theme={theme} size={34} avatar={{ mode: "auto" }} />,
            "默认头像", "首字 + 主题配色", () => setAvatar({ mode: "auto", image: null }))}
          {opt("hidden", <EyeInvisibleOutlined />, "不显示头像", "名字放大顶到头像位", () => setAvatar({ mode: "hidden", image: null }))}
          {opt("image", avatar.mode === "image" && avatar.image
            ? <img src={avatar.image} alt="当前头像" />
            : <CameraOutlined />, "自定义图片", "上传后压缩，仅自己可见", () => fileRef.current?.click())}
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={pickFile} hidden />
        </div>

        <div className="pf-set-section-title">名字</div>
        <Input
          value={name}
          maxLength={20}
          showCount
          placeholder="这个名字会写进人格提示词"
          onChange={(e) => setName(e.target.value)}
        />

        <div className="pf-set-section-title">
          补充人格设定
          <Typography.Text type="secondary"> · 不用重新生成，立即生效</Typography.Text>
        </div>
        <Input.TextArea
          value={extra}
          maxLength={300}
          showCount
          autoSize={{ minRows: 3, maxRows: 6 }}
          placeholder="例如：说话像深夜电台主持人，常用比喻，偶尔停顿；遇到情绪先接住，不急着给方案。"
          onChange={(e) => setExtra(e.target.value)}
        />
        <Typography.Text type="secondary" className="pf-set-note">
          这段会确定性追加到人格的 system_prompt 末尾；想彻底重写人设请用「重建」。
        </Typography.Text>
      </div>
    </Modal>
  );
}
