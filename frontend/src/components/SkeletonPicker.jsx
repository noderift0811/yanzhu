import { useEffect, useState } from "react";
import { Modal, Typography, message } from "antd";
import { CheckCircleFilled } from "@ant-design/icons";
import { request } from "../lib/api.js";

// 换骨架：不重跑工程师 AI，直接套用另一套预置骨架（不含 emoji、不生成图片）
export default function SkeletonPicker({ open, persona, onClose, onSwitched }) {
  const [items, setItems] = useState([]);
  const [picked, setPicked] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");

  const current = persona?.skeleton_id || "";

  useEffect(() => {
    if (!open) return;
    setPicked(current);
    if (items.length) return;
    request("/meta/skeletons")
      .then((data) => setItems(data.items || []))
      .catch((e) => setLoadError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, current]);

  const confirm = async () => {
    if (!persona || !picked || picked === current) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      const updated = await request(`/personas/${persona.id}`, {
        method: "PATCH",
        body: { skeleton_id: picked },
      });
      message.success(`已换成「${updated.skeleton_name || picked}」`);
      onSwitched?.(updated);
    } catch (e) {
      message.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="换一套骨架"
      open={open}
      onCancel={onClose}
      onOk={confirm}
      okText={picked && picked !== current ? "换成这套" : "关闭"}
      cancelText="取消"
      confirmLoading={saving}
      width={760}
      destroyOnClose
    >
      <Typography.Paragraph type="secondary" className="pf-pick-hint">
        换骨架不消耗生成次数，人设、开场白和已有的聊天记录都保留。配色与输入框提示会随风格一并成套替换，
        因为深色骨架配浅色主题会看不清字。
      </Typography.Paragraph>
      {loadError ? (
        <div className="pf-chat-loading">骨架目录加载失败：{loadError}</div>
      ) : (
        <div className="pf-sk-grid">
          {items.map((s) => {
            const on = s.id === current;
            const sel = s.id === picked;
            return (
              <button
                type="button"
                key={s.id}
                className={`pf-sk-card${sel ? " pf-sk-card-sel" : ""}${on ? " pf-sk-card-on" : ""}`}
                onClick={() => setPicked(s.id)}
                aria-pressed={sel}
              >
                {on && <span className="pf-sk-flag">当前</span>}
                {sel && !on && <CheckCircleFilled className="pf-sk-tick" />}
                <span className="pf-sk-name">{s.name}</span>
                <span className="pf-sk-visual">{s.visual}</span>
                <span className="pf-sk-fit">{s.fit}</span>
              </button>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
