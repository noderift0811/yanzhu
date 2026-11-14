import { useState } from "react";
import { Badge, Button, Drawer, Switch, Tag, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { formatSwitchAt, patchTone, useMe } from "../lib/me.js";

// 悬浮球 = 场景内的调参台。刻意只放「点了立刻生效、不耗生成配额」的两类动作：
// 语气开关（拼运行时指令）与换场景（受冷却约束的入口）。
// 重写人设要走工程师模型 30 秒，那种动作放在人格详情页，不挂在这里。
const TONES = [
  { key: "calm", label: "更沉稳", hint: "先承接再回应，不急着给方案" },
  { key: "brief", label: "更简短", hint: "三句以内，能一句说完就不写第二句" },
  { key: "no_exclaim", label: "不用感叹号", hint: "也不加「呢 / 哦 / 呀」这类语气词" },
];

export default function AssistantFab() {
  const me = useMe();
  const navigate = useNavigate();
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
        title="调整当前场景与语气"
        aria-label="打开调整面板"
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
        {active > 0 && <span className="pf-fab-dot">{active}</span>}
      </button>

      <Drawer
        open={open}
        onClose={() => setOpen(false)}
        title="工作台"
        width={340}
        className="pf-fab-drawer"
      >
        <div className="pf-fab-section">
          <Typography.Text type="secondary" className="pf-fab-label">
            当前场景
          </Typography.Text>
          <div className="pf-fab-scene">
            <span className="pf-fab-scene-name">{me?.scene_name || "未选择"}</span>
            {me?.is_demo ? (
              <Tag color="blue">演示账号</Tag>
            ) : me?.can_switch ? (
              <Tag color="green">可切换</Tag>
            ) : (
              <Tag>{formatSwitchAt(me?.next_switch_at) || "冷却中"}后可换</Tag>
            )}
          </div>
          <Typography.Paragraph type="secondary" className="pf-fab-hint">
            场景决定检索语料与安全边界，是这个账号唯一的入口。
          </Typography.Paragraph>
          <Button size="small" onClick={() => { setOpen(false); navigate("/scene"); }}>
            查看场景与切换规则
          </Button>
        </div>

        <div className="pf-fab-section">
          <Typography.Text type="secondary" className="pf-fab-label">
            对话语气{active > 0 ? `（${active} 项生效）` : ""}
          </Typography.Text>
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
          <Typography.Paragraph type="secondary" className="pf-fab-hint">
            语气只改变说法，不改身份与安全边界；立即生效，不消耗生成次数。
          </Typography.Paragraph>
        </div>

        <div className="pf-fab-section">
          <Typography.Text type="secondary" className="pf-fab-label">
            外观
          </Typography.Text>
          <Typography.Paragraph type="secondary" className="pf-fab-hint">
            换骨架、配色与字体在人格页右侧的「主题」面板里，那里能直接看到改动效果。
          </Typography.Paragraph>
          <Button size="small" onClick={() => { setOpen(false); navigate("/personas"); }}>
            去人格库
          </Button>
        </div>
      </Drawer>
    </>
  );
}
