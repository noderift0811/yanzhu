import { lazy, Suspense, useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider, Spin } from "antd";
import zhCN from "antd/locale/zh_CN";
import { bootstrapAuth } from "./lib/api.js";
import LoginPage from "./pages/LoginPage.jsx";

// 路由级代码分割：登录页为首屏保持直载，其余页面按需加载
const HomePage = lazy(() => import("./pages/HomePage.jsx"));
const PersonasPage = lazy(() => import("./pages/PersonasPage.jsx"));
const ChatPage = lazy(() => import("./pages/ChatPage.jsx"));
// 骨架画廊：纯 mock 数据、不请求后端，用于随时比对 16 套骨架
const SkeletonGalleryPage = lazy(() => import("./pages/SkeletonGalleryPage.jsx"));

function Boot() {
  return (
    <div className="pf-boot">
      <Spin size="large" tip="正在恢复会话…">
        <div className="pf-boot-ph" />
      </Spin>
    </div>
  );
}

function Guard({ children }) {
  const [state, setState] = useState({ ready: false, ok: false });

  useEffect(() => {
    let live = true;
    bootstrapAuth().then((ok) => {
      if (live) setState({ ready: true, ok });
    });
    return () => {
      live = false;
    };
  }, []);

  if (!state.ready) return <Boot />;
  if (!state.ok) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{ token: { colorPrimary: "#4f46e5", borderRadius: 8 } }}
    >
      <HashRouter>
        <Suspense fallback={<Boot />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/gallery" element={<SkeletonGalleryPage />} />
            <Route path="/" element={<Guard><HomePage /></Guard>} />
            <Route path="/personas" element={<Guard><PersonasPage /></Guard>} />
            <Route path="/chat/:id" element={<Guard><ChatPage /></Guard>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </HashRouter>
    </ConfigProvider>
  );
}
