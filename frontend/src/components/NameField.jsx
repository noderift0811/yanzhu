import { Input, Typography } from "antd";

// 角色名字段：向导确认页与「重新生成」弹窗共用。
// 留空＝交给工程师 AI 起名；填了就是硬约束，落库前后端还会再强制覆盖一次。
export default function NameField({ value, onChange, label = "角色名字", hint }) {
  return (
    <div className="pf-name-field">
      <div className="pf-name-head">
        <Typography.Text strong className="pf-name-label">
          {label}
        </Typography.Text>
        <Typography.Text type="secondary" className="pf-name-hint">
          {hint || "可留空，交给工程师 AI 起名；之后也能在人格库里改"}
        </Typography.Text>
      </div>
      <Input
        value={value || ""}
        onChange={(e) => onChange(e.target.value.slice(0, 20))}
        placeholder="比如：沈砚、周叔、凌晨三点的电台"
        maxLength={20}
        allowClear
      />
    </div>
  );
}
