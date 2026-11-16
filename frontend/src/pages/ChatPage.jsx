import { useEffect, useState } from "react";
import { Button, Empty, Spin, message } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { request } from "../lib/api.js";
import BuildReveal from "../components/BuildReveal.jsx";
import ChatView from "../components/ChatView.jsx";
import SiteFooter from "../components/SiteFooter.jsx";

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
        <div className="pf-chat-loading">
          <Spin />
        </div>
      </div>
    );
  }

  if (!persona) {
    return (
      <div className="pf-home">
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
      {replay ? (
        <BuildReveal persona={persona} onDone={() => setReplay(false)} />
      ) : (
        <>
          <ChatView
            persona={persona}
            onPersonaChange={setPersona}
            onBack={() => navigate("/personas")}
          />
          <SiteFooter />
        </>
      )}
    </div>
  );
}
