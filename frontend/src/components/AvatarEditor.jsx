import { useRef, useState } from "react";
import { Popover, Typography, message } from "antd";
import { CheckOutlined, CameraOutlined, EyeInvisibleOutlined, UserOutlined } from "@ant-design/icons";
import { request } from "../lib/api.js";
import Avatar from "./Avatar.jsx";
import "../styles/avatar-editor.css";

// 图片压缩参数：160×160 正方形 + JPEG 0.82。
// 项目默认零图片零 base64；这里是用户主动上传，压缩后约 8-20KB，
// 既能放进 SQLite 的 spec_json，也不会让导出的单文件 HTML 体积失控。
const IMG_SIZE = 160;
const IMG_QUALITY = 0.82;

function compressImage(file) {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith("image/")) {
      reject(new Error("请选择图片文件"));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取图片失败"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("图片解析失败"));
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = IMG_SIZE;
        canvas.height = IMG_SIZE;
        const ctx = canvas.getContext("2d");
        // 居中裁剪成正方形，避免变形
        const side = Math.min(img.width, img.height);
        const sx = (img.width - side) / 2;
        const sy = (img.height - side) / 2;
        ctx.drawImage(img, sx, sy, side, side, 0, 0, IMG_SIZE, IMG_SIZE);
        const dataUrl = canvas.toDataURL("image/jpeg", IMG_QUALITY);
        resolve(dataUrl);
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

// 头像编辑器：包在 Avatar 外面，点头像弹就地浮层。
// 三种模式：auto（首字渐变）/ hidden（不显示）/ image（自定义图片）。
// 选完即刻 PATCH 保存（不调 LLM、不耗配额），并通过 onChanged 把更新后的人格回传。
export default function AvatarEditor({ persona, size = 40, theme, avatar: avatarProp, children, onChanged }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);
  const avatar = avatarProp || persona?.avatar || { mode: "auto", image: null };

  const save = async (next) => {
    setSaving(true);
    try {
      const updated = await request(`/personas/${persona.id}`, {
        method: "PATCH",
        body: { avatar: next },
      });
      onChanged?.(updated);
      return true;
    } catch (e) {
      message.error(e.message || "头像设置失败");
      return false;
    } finally {
      setSaving(false);
    }
  };

  const pickAuto = async () => {
    if (await save({ mode: "auto", image: null })) setOpen(false);
  };
  const pickHidden = async () => {
    if (await save({ mode: "hidden", image: null })) setOpen(false);
  };
  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // 允许重复选同一张
    if (!file) return;
    try {
      const dataUrl = await compressImage(file);
      if (await save({ mode: "image", image: dataUrl })) setOpen(false);
    } catch (err) {
      message.error(err.message || "图片处理失败");
    }
  };

  const content = (
    <div className="pf-avatar-editor" role="menu">
      <div className="pf-avatar-editor-title">设置头像</div>
      <button type="button" className="pf-av-opt" onClick={pickAuto} disabled={saving}>
        <Avatar name={persona?.name} theme={theme} size={34} avatar={{ mode: "auto" }} />
        <span className="pf-av-opt-label">默认头像<span>人格首字 + 主题配色</span></span>
        {avatar.mode === "auto" && <CheckOutlined className="pf-av-opt-check" />}
      </button>
      <button type="button" className="pf-av-opt" onClick={pickHidden} disabled={saving}>
        <span className="pf-av-opt-icon"><EyeInvisibleOutlined /></span>
        <span className="pf-av-opt-label">不显示头像<span>只留名字，页面更清爽</span></span>
        {avatar.mode === "hidden" && <CheckOutlined className="pf-av-opt-check" />}
      </button>
      <button type="button" className="pf-av-opt" onClick={() => fileRef.current?.click()} disabled={saving}>
        <span className="pf-av-opt-icon">
          {avatar.mode === "image" && avatar.image
            ? <img src={avatar.image} alt="当前头像" />
            : <CameraOutlined />}
        </span>
        <span className="pf-av-opt-label">自定义图片<span>上传后自动压缩，仅自己可见</span></span>
        {avatar.mode === "image" && <CheckOutlined className="pf-av-opt-check" />}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={onFile}
        hidden
      />
      <Typography.Text type="secondary" className="pf-avatar-editor-note">
        设置跟随这个人格，不耗生成次数。
      </Typography.Text>
    </div>
  );

  return (
    <Popover
      content={content}
      open={open}
      onOpenChange={setOpen}
      trigger="click"
      placement="bottomLeft"
      arrow
      overlayClassName="pf-avatar-popover"
    >
      {children || (
        <Avatar
          name={persona?.name}
          theme={theme}
          size={size}
          avatar={avatar}
        />
      )}
    </Popover>
  );
}
