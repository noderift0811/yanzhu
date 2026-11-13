// 头像 = 人格首字 + 主题渐变，零图片零 base64
export default function Avatar({ name, theme, size = 44 }) {
  const initial = (name || "?").trim().charAt(0) || "?";
  const c1 = theme?.primary || "#4f46e5";
  const c2 = theme?.accent || "#7c6cf0";
  return (
    <span
      className="pf-avatar"
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.46),
        // slop-ok: 双色渐变是方案锁定的人格身份生成机制（主题 primary→accent 派生），
        // 不是装饰渐变；缩略图尺度下用户靠色相差区分人格，删了它将无法互相分辨
        background: `linear-gradient(135deg, ${c1}, ${c2})`,
      }}
    >
      {initial}
    </span>
  );
}
