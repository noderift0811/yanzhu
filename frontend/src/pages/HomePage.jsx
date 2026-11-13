import { useEffect, useState } from "react";
import { Button, Card, Input, Space, Steps, Typography, message } from "antd";
import { request } from "../lib/api.js";
import AppHeader from "../components/AppHeader.jsx";
import TagEditor from "../components/TagEditor.jsx";
import NameField from "../components/NameField.jsx";
import BuildReveal from "../components/BuildReveal.jsx";
import ChatView from "../components/ChatView.jsx";
import PresetPicker from "../components/PresetPicker.jsx";
import AgentBuildView from "../components/AgentBuildView.jsx";
import { EXAMPLES } from "../data/tagGroups.js";

const EMPTY = { tags: [], free_text: "", name: "" };

// 首页 = 工位：三态原地切换（输入向导态 → 建造中态 → 人格聊天态），不跳路由、不刷新页面
export default function HomePage() {
  const [mode, setMode] = useState("wizard"); // wizard | building | agent | chat
  const [persona, setPersona] = useState(null);
  const [preset, setPreset] = useState(null); // 选中的场景预设；null = 走原自由生成路径
  const [agentBody, setAgentBody] = useState(null);
  const [agentQuery, setAgentQuery] = useState(""); // 演示输入：驱动检索与输入护栏
  const [creating, setCreating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [step, setStep] = useState(0);
  const [brief, setBrief] = useState(EMPTY);

  const valid = brief.tags.length > 0 || brief.free_text.trim().length > 0;

  // 工程师 AI 是推理模型，首次生成约 30 秒：给用户一个会走字的施工状态，而不是干等的按钮
  useEffect(() => {
    if (!creating) {
      setElapsed(0);
      return undefined;
    }
    const t = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [creating]);

  const applyExample = (example) => {
    setPreset(null); // 示例与场景预设互斥：混用会得到一组互相打架的限定词
    setBrief({ tags: example.tags, free_text: example.free_text, name: "" });
    setStep(1);
  };

  const applyPreset = (p) => {
    if (!p || p.id === "free") {
      setPreset(null);
      setBrief(EMPTY);
      setAgentQuery("");
      setStep(0);
      return;
    }
    setPreset(p);
    setBrief({ tags: [...p.tags], free_text: p.free_text, name: "" });
    setAgentQuery(p.sample_prompt || "");
    setStep(1);
  };

  const create = async () => {
    if (!valid || creating) return;
    const payload = {
      tags: brief.tags,
      free_text: brief.free_text,
      // 空字符串不传：后端把「没填」和「填了个空名字」当同一件事，别让它撞 min_length
      name: brief.name.trim() || undefined,
    };
    // 选了场景就走五步 Agent 链路；没选场景时行为与改造前完全一致。
    if (preset && preset.id !== "free") {
      setAgentBody({ ...payload, preset_id: preset.id, user_query: agentQuery.trim() || preset.sample_prompt || "" });
      setMode("agent");
      return;
    }
    setCreating(true);
    try {
      const created = await request("/personas", { method: "POST", body: payload });
      setPersona(created);
      setMode("building");
    } catch (e) {
      message.error(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="pf-home">
      <AppHeader />

      {mode === "wizard" && (
        <Card className="pf-wizard">
          <PresetPicker value={preset} onChange={applyPreset} />
          <Steps
            current={step}
            items={[{ title: "选择标签" }, { title: "补充描述" }, { title: "生成人格" }]}
            className="pf-steps"
          />
          {step === 0 && (
            <>
              <Typography.Paragraph type="secondary">
                先点选贴合你想象的性格标签，至少选一个；也可以先用示例起手。
              </Typography.Paragraph>
              <TagEditor value={brief} onChange={setBrief} />
              <Space wrap className="pf-wizard-actions">
                {EXAMPLES.map((ex) => (
                  <Button key={ex.label} size="small" onClick={() => applyExample(ex)}>
                    示例：{ex.label}
                  </Button>
                ))}
                <Button type="primary" disabled={!valid} onClick={() => setStep(1)}>
                  下一步
                </Button>
              </Space>
            </>
          )}
          {step === 1 && (
            <>
              <Typography.Paragraph type="secondary">
                补充这个人格的说话风格、口癖或禁忌（可跳过，直接进入生成）。
              </Typography.Paragraph>
              <TagEditor value={brief} onChange={setBrief} />
              <Space className="pf-wizard-actions">
                <Button onClick={() => setStep(0)}>上一步</Button>
                <Button type="primary" disabled={!valid} onClick={() => setStep(2)}>
                  下一步
                </Button>
              </Space>
            </>
          )}
          {step === 2 && (
            <>
              <Typography.Paragraph>
                {preset
                  ? `「${preset.name}」场景已就绪，Agent 将检索场景知识、规划边界，再生成专属页面。`
                  : "确认限定词，工程师 AI 将生成人设与专属页面。"}
              </Typography.Paragraph>
              <NameField value={brief.name} onChange={(name) => setBrief((b) => ({ ...b, name }))} />
              {preset && (
                <div className="ag-query">
                  <Typography.Text strong>演示输入（会先经过检索与安全护栏）</Typography.Text>
                  <Typography.Paragraph type="secondary" className="ag-query-hint">
                    现场改成任意表达即可验证：口语化危机表述会命中求助资源，医疗越界措辞会被记录。
                    它只影响本次检索与护栏，不写进人格。
                  </Typography.Paragraph>
                  <Input.TextArea
                    rows={2}
                    maxLength={200}
                    showCount
                    value={agentQuery}
                    onChange={(e) => setAgentQuery(e.target.value)}
                    placeholder="写一句这个场景下用户可能说的话…"
                  />
                </div>
              )}
              <Card size="small" type="inner" className="pf-brief-summary">
                <Typography.Text strong>已选标签：</Typography.Text>
                <Space wrap>
                  {brief.tags.map((t) => (
                    <span key={t} className="pf-tag pf-tag-on">
                      {t}
                    </span>
                  ))}
                </Space>
                {brief.free_text.trim() && (
                  <Typography.Paragraph type="secondary" className="pf-brief-text">
                    补充：{brief.free_text}
                  </Typography.Paragraph>
                )}
              </Card>
              <Space className="pf-wizard-actions">
                <Button onClick={() => setStep(1)}>上一步</Button>
                <Button type="primary" loading={creating} onClick={create}>
                  {preset ? "启动五步 Agent 生成" : "让人格 AI 搭建页面"}
                </Button>
              </Space>
              {creating && (
                <div className="pf-build-hint">
                  工程师 AI 正在挑骨架、调色、起名字… 已用 {elapsed}s
                  <span className="pf-build-hint-sub">首次生成约 30 秒，它会先想清楚再动手</span>
                </div>
              )}
            </>
          )}
        </Card>
      )}

      {mode === "agent" && agentBody && (
        <AgentBuildView
          body={agentBody}
          preset={preset}
          onDone={(p) => {
            setPersona(p);
            setMode("chat");
          }}
          onBack={() => {
            setMode("wizard");
            setStep(2);
          }}
        />
      )}

      {mode === "building" && persona && (
        <BuildReveal persona={persona} onDone={() => setMode("chat")} />
      )}

      {mode === "chat" && persona && (
        <ChatView persona={persona} onPersonaChange={setPersona} onBack={() => setMode("wizard")} />
      )}
    </div>
  );
}
