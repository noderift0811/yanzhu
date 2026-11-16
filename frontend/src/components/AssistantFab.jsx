import { useState } from "react";
import { Modal, Switch, Typography, message } from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { patchTone, useMe } from "../lib/me.js";
import { useDecoration } from "../lib/decoration.js";
import AiDecorator from "./AiDecorator.jsx";

// 悬浮球 = 场景内的装修台。刻意只放界面里没有、且点了不耗生成配额的动作：
// ① AI 装修师（一句话让 AI 改配色，实时预览后采用）；② 对话语气快捷开关。
// 换骨架 / 调配色在聊天页头部「外观」，换场景在「站点」下拉——那些是界面已有的入口，
// 不再在这里重复，避免用户两处看到同一个功能、也不知道该点哪个。
// 重写人设要走工程师模型，那种动作放在人格详情页。
const TONES = [
  { key: "calm", label: "更沉稳", hint: "先承接再回应，不急着给方案" },
  { key: "brief", label: "更简短", hint: "三句以内，能一句说完就不写第二句" },
  { key: "no_exclaim", label: "不用感叹号", hint: "也不加「呢 / 哦 / 呀」这类语气词" },
];

export default function AssistantFab() {
  const me = useMe();
  const deco = useDecoration(); // 聊天页登记后非 null：此刻浮窗就是 AI 装修台
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState("");

  const tone = me?.tone || {};
  const active = TONES.filter((t) => tone[t.key]).length;

  const toggle = async (key, checked) => {
    setSaving(key);
    try {
      await patchTone({ [key]: checked });
      message.success(checked ? "已开启，下一条回复生效" : "已关闭");
    } catch (e) {
      message.error(e.message);
    } finally {
      setSaving("");
    }
  };

  return (
    <>
      <button
        type="button"
        className="pf-fab"
        onClick={() => setOpen(true)}
        title={deco ? "AI 装修台：一句话改界面" : "调整对话语气"}
        aria-label="打开装修台"
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path
            d="M4 7h10M18 7h2M4 17h4M12 17h8M4 12h16"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="16" cy="7" r="2.2" stroke="currentColor" strokeWidth="1.8" fill="none" />
          <circle cx="10" cy="17" r="2.2" stroke="currentColor" strokeWidth="1.8" fill="none" />
        </svg>
        {deco ? (
          <span className="pf-fab-dot pf-fab-dot-deco">AI</span>
        ) : active > 0 ? (
          <span className="pf-fab-dot">{active}</span>
        ) : null}
      </button>

      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        title={
          <span className="pf-fab-modal-title">
            <RobotOutlined /> AI 装修台
            <span className="pf-fab-modal-sub">一句话，就能改这个页面的样子</span>
          </span>
        }
        footer={null}
        width={560}
        className="pf-fab-modal"
        centered
        destroyOnClose
      >
        <AiDecorator deco={deco} />

        <div className="pf-fab-section pf-fab-tone-section">
          <Typography.Text type="secondary" className="pf-fab-label">
            对话语气{active > 0 ? `（${active} 项生效）` : ""}
          </Typography.Text>
          <div className="pf-fab-tone-grid">
            {TONES.map((t) => (
              <div key={t.key} className="pf-fab-row">
                <div>
                  <div className="pf-fab-row-title">{t.label}</div>
                  <div className="pf-fab-row-hint">{t.hint}</div>
                </div>
                <Switch
                  size="small"
                  checked={!!tone[t.key]}
                  loading={saving === t.key}
                  onChange={(v) => toggle(t.key, v)}
                />
              </div>
            ))}
          </div>
          <Typography.Paragraph type="secondary" className="pf-fab-hint">
            语气只改变说法，不改身份与安全边界；立即生效，不消耗生成次数。
          </Typography.Paragraph>
        </div>
      </Modal>
    </>
  );
}
