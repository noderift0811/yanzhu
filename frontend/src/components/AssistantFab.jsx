import { useState } from "react";
import { Button, Drawer, Switch, Tag, Typography, message } from "antd";
import { BgColorsOutlined, SwapOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { formatSwitchAt, patchTone, useMe } from "../lib/me.js";
import { useDecoration } from "../lib/decoration.js";

// 悬浮球 = 场景内的装修台。只放「点了立刻生效、不耗生成配额」的动作：
// 语气开关（拼运行时指令）、换场景（受冷却约束的入口），
// 以及在专属页面里就地换骨架/调配色——这两个面板由聊天页持有，悬浮球经 decoration
// 桥接就地打开，实时预览与保存仍走聊天页原逻辑，不跳页、不重复实现。
// 重写人设要走工程师模型，那种动作放在人格详情页，不挂在这里。
const TONES = [
  { key: "calm", label: "更沉稳", hint: "先承接再回应，不急着给方案" },
  { key: "brief", label: "更简短", hint: "三句以内，能一句说完就不写第二句" },
  { key: "no_exclaim", label: "不用感叹号", hint: "也不加「呢 / 哦 / 呀」这类语气词" },
];

export default function AssistantFab() {
  const me = useMe();
  const navigate = useNavigate();
  const deco = useDecoration(); // 聊天页登记后非 null：此刻悬浮球就是装修台
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
        title={deco ? "装修台：语气 · 配色 · 骨架" : "调整当前场景与语气"}
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
        {deco ? (
          <span className="pf-fab-dot pf-fab-dot-deco">装</span>
        ) : active > 0 ? (
          <span className="pf-fab-dot">{active}</span>
        ) : null}
      </button>

      <Drawer
        open={open}
        onClose={() => setOpen(false)}
        title={deco ? "装修台" : "工作台"}
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
            外观装修
          </Typography.Text>
          {deco ? (
            <>
              <div className="pf-fab-deco-now">
                <span className="pf-fab-deco-name">{deco.persona?.name || "当前页面"}</span>
                {deco.skeletonName && <Tag className="pf-fab-deco-sk">{deco.skeletonName}</Tag>}
              </div>
              <Button
                block
                icon={<BgColorsOutlined />}
                className="pf-fab-deco-btn"
                onClick={() => { setOpen(false); deco.openTheme(); }}
              >
                调整配色
              </Button>
              <Button
                block
                icon={<SwapOutlined />}
                className="pf-fab-deco-btn"
                onClick={() => { setOpen(false); deco.openSkeleton(); }}
              >
                换一套骨架
              </Button>
              <Typography.Paragraph type="secondary" className="pf-fab-hint pf-fab-deco-hint">
                就地改动、实时预览，不跳页、不动人设与聊天记录，也不消耗生成次数。
              </Typography.Paragraph>
            </>
          ) : (
            <>
              <Typography.Paragraph type="secondary" className="pf-fab-hint">
                进入某个专属页面后，可在这里就地换骨架、调配色。现在先去人格库挑一个。
              </Typography.Paragraph>
              <Button size="small" onClick={() => { setOpen(false); navigate("/personas"); }}>
                去人格库
              </Button>
            </>
          )}
        </div>
      </Drawer>
    </>
  );
}
