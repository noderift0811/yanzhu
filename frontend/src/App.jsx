import { lazy, Suspense, useEffect, useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import { bootstrapAuth } from "./lib/api.js";
import { loadMe, useMe } from "./lib/me.js";
import LoginPage from "./pages/LoginPage.jsx";
import AssistantFab from "./components/AssistantFab.jsx";

// 路由级代码分割：登录页为首屏保持直载，其余页面按需加载
const HomePage = lazy(() => import("./pages/HomePage.jsx"));
const PersonasPage = lazy(() => import("./pages/PersonasPage.jsx"));
const ChatPage = lazy(() => import("./pages/ChatPage.jsx"));
const ScenePage = lazy(() => import("./pages/ScenePage.jsx"));
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

// allowNoScene：只有 /scene 自己要用，否则「还没选场景」会被自己无限重定向
function Guard({ children, allowNoScene = false }) {
  const [state, setState] = useState({ ready: false, ok: false });
  const me = useMe();

  useEffect(() => {
    let live = true;
    bootstrapAuth()
      .then(async (ok) => {
        if (!ok) return live && setState({ ready: true, ok: false });
        try {
          await loadMe(true);
        } catch {
          /* 401 已由 request 统一处理并跳登录 */
        }
        if (live) setState({ ready: true, ok: true });
      })
      .catch(() => live && setState({ ready: true, ok: false }));
    return () => {
      live = false;
    };
  }, []);

  if (!state.ready) return <Boot />;
  if (!state.ok) return <Navigate to="/login" replace />;
  // 场景是账号级的唯一入口：没选过就先选，其余页面一律进不来
  if (!allowNoScene && me && me.scene_chosen === false) return <Navigate to="/scene" replace />;
  return (
    <>
      {children}
      {/* 选场景页不需要调参台：那里没有当前场景可调，悬浮球只会挡视线 */}
      {!allowNoScene && <AssistantFab />}
    </>
  );
}

export default function App() {
  // antd 主题统一在 main.jsx 的 ConfigProvider（纸感 --yz-* 同源）；
  // 这里原来还有一层 colorPrimary 靛蓝的旧 Provider，会把外壳又刷回默认蓝，已删。
  return (
    <HashRouter>
        <Suspense fallback={<Boot />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/gallery" element={<SkeletonGalleryPage />} />
            <Route path="/scene" element={<Guard allowNoScene><ScenePage /></Guard>} />
            <Route path="/" element={<Guard><HomePage /></Guard>} />
            <Route path="/personas" element={<Guard><PersonasPage /></Guard>} />
            <Route path="/chat/:id" element={<Guard><ChatPage /></Guard>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </HashRouter>
  );
}
