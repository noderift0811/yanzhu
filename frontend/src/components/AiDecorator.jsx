import { useEffect, useRef, useState } from "react";
import { Button, Input, Typography, message } from "antd";
import {
  RobotOutlined, SendOutlined, CheckOutlined, ReloadOutlined,
  ThunderboltOutlined, LoadingOutlined,
} from "@ant-design/icons";
import { request } from "../lib/api.js";
import { useThemeVars } from "../hooks/useThemeVars.js";
import { readableOn } from "../lib/theme.js";
import "../styles/ai-decorator.css";

// 快捷需求胶囊：点一下直接填进输入框并发送，降低「不知道怎么说」的门槛。
// 文案用大白话，与后端 decorate 的关键词兜底表呼应。
const QUICK = [
  "深夜咖啡馆的暖色调",
  "清爽冷调、极简一点",
  "暖纸书卷、温柔些",
  "粉粉的可爱风",
];

// 结果卡内嵌的迷你预览：让用户在「采用」前就能看到这套配色套到气泡上的样子。
function ResultPreview({ theme }) {
  const { style, className } = useThemeVars(theme);
  const onPrimary = readableOn(theme.primary);
  return (
    <div className={`ai-dec-preview ${className}`} style={style}>
      <div className="ai-dec-prev-bar">
        <i style={{ background: theme.primary }} />
        <span style={{ color: theme.text }}>效果预览</span>
      </div>
      <div className="ai-dec-prev-body">
        <p className="ai-dec-prev-a" style={{ background: theme.surface, color: theme.text }}>你来得正好，坐吧。</p>
        <p className="ai-dec-prev-u" style={{ background: theme.primary, color: onPrimary }}>今天有点累。</p>
      </div>
      <div className="ai-dec-prev-swatches">
        {["primary", "accent", "bg", "surface", "text"].map((k) => (
          <i key={k} style={{ background: theme[k] }} title={k} />
        ))}
      </div>
    </div>
  );
}

// AI 装修师：悬浮球装修台里的第一屏。输入自然语言 → AI 产出主题 → 实时预览 → 采用落库。
// deco 是聊天页通过 decoration store 登记的 handle（含 persona 与预览/保存通道）。
export default function AiDecorator({ deco }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); // { theme, note, model, mock }
  const inputRef = useRef(null);

  // 抽屉关闭/组件卸载时，若还有未采用的预览，撤销掉，避免草稿主题残留。
  useEffect(() => () => { deco?.resetPreview?.(); }, [deco]);

  const submit = async (text) => {
    const want = (text ?? input).trim();
    if (!want || !deco?.persona) return;
    setLoading(true);
    setResult(null);
    try {
      const persona = deco.persona;
      const theme = persona?.spec?.theme || persona?.theme;
      const data = await request("/decorate", {
        method: "POST",
        body: {
          request: want,
          theme,
          skeleton_id: persona?.skeleton_id || null,
        },
      });
      setResult(data);
      setInput("");
      // 立刻实时套到当前页面；用户没点「采用」前不做任何持久化。
      deco.previewTheme?.(data.theme);
    } catch (e) {
      message.error(e.message || "AI 装修失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  const apply = async () => {
    if (!result || !deco) return;
    setLoading(true);
    try {
      await deco.applyTheme(result.theme);
      message.success("已采用，新配色已保存");
      setResult(null);
    } catch (e) {
      message.error(e.message || "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const retry = () => {
    deco.resetPreview?.();
    setResult(null);
    inputRef.current?.focus();
  };

  if (!deco?.persona) {
    return (
      <div className="pf-fab-section">
        <Typography.Text type="secondary" className="pf-fab-label">
          <RobotOutlined /> AI 装修师
        </Typography.Text>
        <Typography.Paragraph type="secondary" className="pf-fab-hint ai-dec-off">
          进入某个专属页面后，用一句话告诉 AI 你想要的风格，它就地帮你改。现在先去人格库挑一个。
        </Typography.Paragraph>
      </div>
    );
  }

  return (
    <div className="pf-fab-section ai-dec-section">
      <Typography.Text type="secondary" className="pf-fab-label">
        <RobotOutlined /> AI 装修师
        <span className="ai-dec-badge">一句话改界面</span>
      </Typography.Text>
      <Typography.Paragraph type="secondary" className="pf-fab-hint ai-dec-lead">
        说说你想要的风格，AI 会当场改好配色与气质，满意再采用。不改人设与聊天记录，不消耗生成次数。
      </Typography.Paragraph>

      <div className="ai-dec-quick">
        {QUICK.map((q) => (
          <button
            key={q}
            type="button"
            className="ai-dec-chip"
            disabled={loading}
            onClick={() => submit(q)}
          >
            <ThunderboltOutlined /> {q}
          </button>
        ))}
      </div>

      <div className="ai-dec-input-row">
        <Input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={() => submit()}
          placeholder="例：像深夜电台那样暖暖的…"
          maxLength={200}
          disabled={loading}
          aria-label="描述你想要的界面风格"
        />
        <Button
          type="primary"
          icon={loading ? <LoadingOutlined /> : <SendOutlined />}
          onClick={() => submit()}
          disabled={loading || !input.trim()}
          aria-label="让 AI 装修"
        />
      </div>

      {result && (
        <div className="ai-dec-result">
          <div className="ai-dec-result-head">
            <RobotOutlined /> AI 说：{result.note}
          </div>
          <ResultPreview theme={result.theme} />
          <div className="ai-dec-result-foot">
            <Button size="small" onClick={retry} icon={<ReloadOutlined />} disabled={loading}>
              重来
            </Button>
            <Button size="small" type="primary" onClick={apply} icon={<CheckOutlined />} loading={loading}>
              采用这套
            </Button>
          </div>
          <div className="ai-dec-result-meta">
            {result.mock ? "演示模式配色" : `AI · ${result.model}`}
            {" · 未保存前只是预览"}
          </div>
        </div>
      )}
    </div>
  );
}
