import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发 / 预览均走代理，前端零密钥、零直连 LLM
// 端口策略：本机常驻其它项目（评估系统占用 8000/4173/5173），言筑固定让到
// 后端 8100、预览 4180、开发 5180。要改端口时同步改 start.bat 与 share.py。
const BACKEND_TARGET = process.env.YANZHU_BACKEND || "http://127.0.0.1:8100";

const apiProxy = {
  "/api": { target: BACKEND_TARGET, changeOrigin: true },
};

// 公网分享时必须放行隧道域名：cpolar 会改写 Host 头（-host-header=localhost），
// 但 localhost.run 走 ssh 转发，原样透传 Host，Vite 5.4.12+ 会以 403 拦掉
// 未登记的域名。这里按后缀白名单放行，不用 allowedHosts: true（避免全放行）。
const TUNNEL_HOSTS = [".lhr.life", ".localhost.run", ".cpolar.top", ".cpolar.cn"];

export default defineConfig({
  plugins: [react()],
  // host 必须显式写 127.0.0.1：默认的 localhost 在 Windows 上常被 Node 解析成 ::1，
  // 只绑 IPv6 回环，浏览器访问 127.0.0.1 就会 ERR_CONNECTION_REFUSED。
  // strictPort：端口被占时直接报错，而不是悄悄漂到下一个端口导致 start.bat 打开的地址失效。
  server: {
    host: "127.0.0.1", port: 5180, strictPort: true, proxy: apiProxy,
    allowedHosts: TUNNEL_HOSTS,
  },
  preview: {
    host: "127.0.0.1", port: 4180, strictPort: true, proxy: apiProxy,
    allowedHosts: TUNNEL_HOSTS,
  },
});
