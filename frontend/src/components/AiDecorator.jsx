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

// 思考过程的文案，对应后端 pipeline/decorate.py 的真实步骤：
// prompt 构造 → 快模型生成 → 对比度护栏 → 兜底 → 产出预览。
// 接口是一次性返回（非流式），这里用定时逐条点亮把等待过程可视化，不假装编造结果。
const THINK_STEPS = [
  "读懂你的描述与情绪",
  "匹配当前骨架的气质",
  "生成配色与字体方案",
  "校验文字对比度",
  "铺成可预览的页面",
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
  const [thinkStep, setThinkStep] = useState(-1); // 当前思考步骤下标，-1 表示不在思考
  const inputRef = useRef(null);
  const thinkTimer = useRef(null);

  // 抽屉关闭/组件卸载时，若还有未采用的预览，撤销掉，避免草稿主题残留；同时清掉思考计时器。
  useEffect(() => () => {
    if (thinkTimer.current) clearInterval(thinkTimer.current);
    deco?.resetPreview?.();
  }, [deco]);

  const stopThinking = () => {
    if (thinkTimer.current) {
      clearInterval(thinkTimer.current);
      thinkTimer.current = null;
    }
  };

  const submit = async (text) => {
    const want = (text ?? input).trim();
    if (!want || !deco?.persona) return;
    setLoading(true);
    setResult(null);
    // 逐条点亮思考步骤：约每 0.7s 前进一步，停在最后一步等接口返回，绝不提前编造结果。
    setThinkStep(0);
    stopThinking();
    thinkTimer.current = setInterval(() => {
      setThinkStep((s) => Math.min(s + 1, THINK_STEPS.length - 1));
    }, 700);
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
      stopThinking();
      setThinkStep(-1);
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
      <div className="ai-dec-hero ai-dec-hero-off">
        <div className="ai-dec-hero-icon"><RobotOutlined /></div>
        <div>
          <div className="ai-dec-hero-title">AI 装修师</div>
          <Typography.Paragraph type="secondary" className="ai-dec-hero-desc">
            进入某个专属页面后，用一句话告诉 AI 你想要的风格，它就地帮你改。现在先去人格库挑一个。
          </Typography.Paragraph>
        </div>
      </div>
    );
  }

  return (
    <div className="ai-dec-wrap">
      <div className="ai-dec-hero">
        <div className="ai-dec-hero-icon"><RobotOutlined /></div>
        <div className="ai-dec-hero-text">
          <div className="ai-dec-hero-title">
            告诉 AI 你想要什么样的页面
            <span className="ai-dec-badge">实时生效</span>
          </div>
          <Typography.Paragraph type="secondary" className="ai-dec-hero-desc">
            用大白话描述气质或颜色，AI 当场改好配色与字体，页面立刻变给你看。满意再点采用——不改人设与聊天记录，不消耗生成次数。
          </Typography.Paragraph>
        </div>
      </div>

      <div className="ai-dec-block-label">试试这些，或自己写一句</div>
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

      {loading && thinkStep >= 0 && (
        <div className="ai-dec-thinking" aria-live="polite">
          <div className="ai-dec-thinking-head">
            <LoadingOutlined /> AI 正在思考…
          </div>
          <ol className="ai-dec-thinking-steps">
            {THINK_STEPS.map((step, i) => (
              <li
                key={step}
                className={i < thinkStep ? "done" : i === thinkStep ? "active" : ""}
              >
                <span className="ai-dec-step-dot">
                  {i < thinkStep ? <CheckOutlined /> : i + 1}
                </span>
                {step}
                {i === thinkStep && <span className="ai-dec-step-dots"><i /><i /><i /></span>}
              </li>
            ))}
          </ol>
        </div>
      )}

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
