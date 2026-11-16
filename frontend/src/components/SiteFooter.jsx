import { QrcodeOutlined } from "@ant-design/icons";
import { Typography } from "antd";
import "../styles/site-footer.css";

// 专属网站的页脚：言筑平台信息从顶部退到末尾，让顶部只属于用户搭出来的页面。
// 纸感 token（--yz-*）而非骨架主题——它是平台落款，不该跟着 AI 生成的皮肤变色。
// 二维码先占位：在线隧道地址要临提交才起，届时把占位框换成真二维码即可。
export default function SiteFooter() {
  return (
    <footer className="pf-site-footer">
      <div className="pf-site-footer-inner">
        <div className="pf-site-footer-brand">
          <span className="pf-brand-mark">言</span>
          <div className="pf-site-footer-copy">
            <div className="pf-site-footer-name">言筑 <em>YanZhu</em></div>
            <Typography.Text className="pf-site-footer-slogan">你说，它筑。</Typography.Text>
            <div className="pf-site-footer-sub">16 套手写骨架 · 零代码生成 · 由你亲口用词句搭成</div>
          </div>
        </div>
        <div className="pf-site-footer-qr">
          <div className="pf-site-footer-qrbox" aria-label="扫码访问占位">
            <QrcodeOutlined />
          </div>
          <span className="pf-site-footer-qrcap">扫码访问本站</span>
        </div>
      </div>
      <div className="pf-site-footer-rule">
        本站由言筑生成 · 一段提示词，一个只属于你的页面
      </div>
    </footer>
  );
}
