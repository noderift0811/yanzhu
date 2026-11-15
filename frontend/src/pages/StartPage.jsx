import { useState } from "react";
import { Button, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { useMe } from "../lib/me.js";
import PersonaBriefModal from "../components/PersonaBriefModal.jsx";
import "../styles/start.css";

// 开站页：登录后还没有主页面（人格）时的落点。
// 专属网站模式的「空地」状态——品牌 + 三句话 + 一个开始搭建的入口。
export default function StartPage() {
  const navigate = useNavigate();
  const me = useMe();
  const needScene = me?.scene_chosen === false;
  const [createOpen, setCreateOpen] = useState(false);

  const goBuild = ({ body, preset }) => navigate("/build", { state: { body, preset } });

  return (
    <div className="pf-start">
      <div className="pf-start-inner">
        <div className="pf-start-brand">
          <span className="pf-brand-mark">言</span>
          <span className="pf-start-brand-name">言筑</span>
        </div>

        <Typography.Title level={2} className="pf-start-title">
          这里还没有你的专属页面
        </Typography.Title>

        <div className="pf-start-lede">
          <p>几个限定词，筑成一个能对话的人。</p>
          <p>五步 Agent 链路逐步可见，16 套骨架长成不一样的界面。</p>
          <p>把第一个搭起来——之后每次登录，都会直接回到它。</p>
        </div>

        <div className="pf-start-actions">
          <Button
            type="primary"
            size="large"
            onClick={() => (needScene ? navigate("/scene") : setCreateOpen(true))}
          >
            {needScene ? "选择场景开始搭建" : "开始搭建"}
          </Button>
          {!needScene && (
            <Button size="large" type="text" onClick={() => navigate("/scene")}>
              或先换一个场景
            </Button>
          )}
        </div>
      </div>

      <PersonaBriefModal
        open={createOpen}
        mode="create"
        onCancel={() => setCreateOpen(false)}
        onConfirm={goBuild}
      />
    </div>
  );
}
