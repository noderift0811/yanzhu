import { forwardRef } from "react";

// 头像 = 人格首字 + 主题渐变（默认）/ 自定义图片 / 隐藏（只留占位）。
// 三种模式由人格的 spec.avatar 决定，跟随人格存储；零图片是默认，图片是用户主动上传的压缩 data URL。
// forwardRef + 透传 rest：让 antd Popover 能把 ref 和 onClick 挂到真正的 button 上。
const Avatar = forwardRef(function Avatar({ name, theme, size = 44, avatar, onEdit, onClick, ...rest }, ref) {
  const mode = avatar?.mode || "auto";
  const handleClick = (e) => {
    onClick?.(e);
    onEdit?.(e);
  };

  // hidden：完全不渲染视觉，只占原位（保留尺寸让标题不错位）。点占位仍可打开设置。
  if (mode === "hidden") {
    return (
      <button
        {...rest}
        ref={ref}
        type="button"
        className={`pf-avatar pf-avatar--hidden${onEdit ? " pf-avatar--editable" : ""}${rest.className ? " " + rest.className : ""}`}
        style={{ width: size, height: size, ...rest.style }}
        onClick={handleClick}
        disabled={!onEdit && !onClick}
        title="头像已隐藏，点击设置"
        aria-label="设置头像"
      />
    );
  }

  // image：自定义图片，object-fit cover 撑满圆形。
  if (mode === "image" && avatar?.image) {
    return (
      <button
        {...rest}
        ref={ref}
        type="button"
        className={`pf-avatar pf-avatar--image${onEdit ? " pf-avatar--editable" : ""}${rest.className ? " " + rest.className : ""}`}
        style={{ width: size, height: size, ...rest.style }}
        onClick={handleClick}
        disabled={!onEdit && !onClick}
        title="点击设置头像"
        aria-label="设置头像"
      >
        <img src={avatar.image} alt={name || "头像"} />
        {onEdit && <span className="pf-avatar-edit" aria-hidden="true">✎</span>}
      </button>
    );
  }

  // auto（默认）：人格首字 + primary→accent 双色渐变。
  const initial = (name || "?").trim().charAt(0) || "?";
  const c1 = theme?.primary || "#4f46e5";
  const c2 = theme?.accent || "#7c6cf0";
  return (
    <button
      {...rest}
      ref={ref}
      type="button"
      className={`pf-avatar${onEdit ? " pf-avatar--editable" : ""}${rest.className ? " " + rest.className : ""}`}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.46),
        // slop-ok: 双色渐变是方案锁定的人格身份生成机制（主题 primary→accent 派生），
        // 不是装饰渐变；缩略图尺度下用户靠色相差区分人格，删了它将无法互相分辨
        background: `linear-gradient(135deg, ${c1}, ${c2})`,
        ...rest.style,
      }}
      onClick={handleClick}
      disabled={!onEdit && !onClick}
      title={onEdit || onClick ? "点击设置头像" : undefined}
      aria-label={onEdit || onClick ? "设置头像" : undefined}
    >
      {initial}
      {onEdit && <span className="pf-avatar-edit" aria-hidden="true">✎</span>}
    </button>
  );
});

export default Avatar;
