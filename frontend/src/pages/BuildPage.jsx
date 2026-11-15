import { Navigate, useLocation, useNavigate } from "react-router-dom";
import AgentBuildView from "../components/AgentBuildView.jsx";

// 五步施工直播页：弹窗确认后跳到这里，全屏复用 AgentBuildView。
// body 与 preset 由路由 state 带入；刷新后 state 丢失（施工中途不该刷新），
// 兜底回人格库。
export default function BuildPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { body, preset } = location.state || {};

  if (!body) return <Navigate to="/personas" replace />;

  return (
    <div className="pf-home">
      <AgentBuildView
        body={body}
        preset={preset}
        onDone={(persona) => navigate(`/chat/${persona.id}`, { replace: true })}
        onBack={() => navigate("/personas", { replace: true })}
      />
    </div>
  );
}
