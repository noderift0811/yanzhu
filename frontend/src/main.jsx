import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "antd/dist/reset.css";
import App from "./App.jsx";
import "./styles/theme.css";
import "./styles/skeletons.css";
import "./styles/skeletons-extra.css";
import "./styles/picker.css";
import "./styles/agent.css";
import "./styles/scene.css";

// 外壳的 antd 主题与 theme.css 的 --yz-* 同源：不在这里统一，
// 按钮/输入框/开关会一直是 antd 默认蓝，和纸感外壳打架。
// 16 套骨架的颜色由各自的 --pf-* 内联变量接管，不受这里影响。
const paperTheme = {
  token: {
    colorPrimary: "#b0563a",
    colorInfo: "#b0563a",
    colorLink: "#b0563a",
    colorTextBase: "#2e2a25",
    colorBgBase: "#fffdf8",
    colorBorder: "#e6dccc",
    colorBorderSecondary: "#efe7d9",
    borderRadius: 8,
    fontFamily:
      '-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Button: { fontWeight: 500 },
    Card: { borderRadiusLG: 14 },
    Tabs: { itemSelectedColor: "#93452e", inkBarColor: "#b0563a" },
    Switch: { colorPrimary: "#3f5d54", colorPrimaryHover: "#334b44" },
  },
};

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={paperTheme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
