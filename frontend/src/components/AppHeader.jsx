import { useCallback, useEffect, useState } from "react";
import { Button, Space, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { authStore, request } from "../lib/api.js";
import { resetMe } from "../lib/me.js";

// 非聊天页的公共头部：品牌 + 配额 + 人格库 + 退出
export default function AppHeader({ right }) {
  const navigate = useNavigate();
  const [quota, setQuota] = useState(null);

  const loadQuota = useCallback(() => {
    request("/auth/me")
      .then((d) =>
        setQuota({
          genLeft: d.quota_gen_daily - d.quota_gen_used,
          chatLeft: d.quota_chat_daily - d.quota_chat_used,
        })
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadQuota();
    // 每次对话完成后由 useChat 派发，头部配额就地刷新
    window.addEventListener("pf-quota-changed", loadQuota);
    return () => window.removeEventListener("pf-quota-changed", loadQuota);
  }, [loadQuota]);

  const logout = () => {
    authStore.clear();
    resetMe(); // 不清缓存的话，换账号进来会先闪一下上一个人的场景
    location.hash = "#/login";
  };

  return (
    <header className="pf-app-header">
      <div className="pf-brand" onClick={() => navigate("/")} role="presentation" title="言筑 · 未命名者">
        <span className="pf-brand-mark">言</span>
        <Typography.Text strong>言筑</Typography.Text>
      </div>
      <Space>
        {right}
        {quota && (
          <span className="pf-quota" title="每日配额，跨日自动重置">
            生成 {quota.genLeft} · 对话 {quota.chatLeft}
          </span>
        )}
        <Button size="small" type="text" onClick={() => navigate("/personas")}>
          人格库
        </Button>
        <Button size="small" type="text" onClick={logout}>
          退出
        </Button>
      </Space>
    </header>
  );
}
