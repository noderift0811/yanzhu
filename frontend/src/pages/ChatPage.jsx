import { useEffect, useState } from "react";
import { Button, Empty, Space, Spin, message } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { request } from "../lib/api.js";
import AppHeader from "../components/AppHeader.jsx";
import BuildReveal from "../components/BuildReveal.jsx";
import ChatView from "../components/ChatView.jsx";

// 人格库入口的聊天页：加载后重放建造揭晓（方案：打开/重新生成时重放）
export default function ChatPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [persona, setPersona] = useState(null);
  const [loading, setLoading] = useState(true);
  const [replay, setReplay] = useState(true);

  useEffect(() => {
    let live = true;
    setLoading(true);
    request(`/personas/${id}`)
      .then((data) => {
        if (live) setPersona(data);
      })
      .catch((e) => {
        if (live) message.error(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="pf-home">
        <AppHeader />
        <div className="pf-chat-loading">
          <Spin />
        </div>
      </div>
    );
  }

  if (!persona) {
    return (
      <div className="pf-home">
        <AppHeader />
        <Empty description="人格不存在或已删除">
          <Button type="primary" onClick={() => navigate("/personas")}>
            返回人格库
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div className="pf-home">
      <AppHeader />
      {replay ? (
        <BuildReveal persona={persona} onDone={() => setReplay(false)} />
      ) : (
        <ChatView
          persona={persona}
          onPersonaChange={setPersona}
          onBack={() => navigate("/personas")}
          headerExtra={
            <Space>
              <Button size="small" type="text" onClick={() => setReplay(true)}>
                重看建造
              </Button>
            </Space>
          }
        />
      )}
    </div>
  );
}
