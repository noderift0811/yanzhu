import { useEffect, useRef, useState } from "react";
import { Button, Typography } from "antd";
import { streamSSE } from "../lib/api.js";
import AgentTimeline from "./AgentTimeline.jsx";

const EMPTY = { steps: [], stepState: {}, toolLog: [], guards: [], result: null };

// 负责真正调用 SSE 的容器；展示交给 AgentTimeline。
// 五步状态、工具日志、护栏报告全部来自后端事件，前端不伪造进度。
export default function AgentBuildView({ body, preset, onDone, onBack }) {
  const [runId, setRunId] = useState(0);
  const lastRun = useRef(-1);
  const [steps, setSteps] = useState([]);
  const [stepState, setStepState] = useState({});
  const [toolLog, setToolLog] = useState([]);
  const [guards, setGuards] = useState([]);
  const [result, setResult] = useState(null);
  const [persona, setPersona] = useState(null);
  const [status, setStatus] = useState("running");
  const [error, setError] = useState("");
  const [meta, setMeta] = useState({});

  useEffect(() => {
    // StrictMode 会把 effect 连跑两次；用 runId 去重，避免生成两个人格。
    if (lastRun.current === runId) return undefined;
    lastRun.current = runId;
    setSteps(EMPTY.steps);
    setStepState({});
    setToolLog([]);
    setGuards([]);
    setResult(null);
    setPersona(null);
    setError("");
    setStatus("running");

    streamSSE("/agent/build", {
      method: "POST",
      body,
      onEvent: (event, data) => {
        if (event === "start") {
          setSteps(data.steps || []);
          setMeta({ preset: data.preset, level: data.safety_level, engineer: data.engineer_adapter });
        } else if (event === "step") {
          setStepState((prev) => ({ ...prev, [data.id]: data }));
        } else if (event === "tool") {
          setToolLog((prev) => [...prev, data]);
        } else if (event === "guard") {
          setGuards((prev) => [...prev, data]);
        } else if (event === "result") {
          setResult(data);
        } else if (event === "done") {
          setPersona(data.persona);
          setStatus("done");
        } else if (event === "error") {
          setError(data.message || "链路失败");
          setStatus("error");
        }
      },
    }).catch((e) => {
      setError(e.message || "无法连接生成服务");
      setStatus("error");
    });
    return undefined;
  }, [runId, body]);

  const retry = () => setRunId((n) => n + 1);

  return (
    <div className="ag-build">
      <div className="ag-build-head">
        <div>
          <Typography.Title level={4} className="ag-build-title">
            五步 Agent 正在搭建你的{preset?.name || "专属"}页面
          </Typography.Title>
          <Typography.Text type="secondary">
            检索 · 规划 · 生成 · 校验 · 兜底，每步调用的工具与结论实时可见
            {meta.preset && `　场景 ${meta.preset}　护栏 ${meta.level}　模型 ${meta.engineer}`}
          </Typography.Text>
        </div>
        <span className={`ag-build-status is-${status}`}>
          {status === "running" ? "链路运行中" : status === "done" ? "已生成" : "已中断"}
        </span>
      </div>

      <AgentTimeline
        steps={steps}
        stepState={stepState}
        toolLog={toolLog}
        guards={guards}
        result={result}
      />

      {status === "error" && (
        <div className="ag-build-error">
          <span>{error}</span>
          <Button size="small" onClick={retry}>重试链路</Button>
          <Button size="small" type="text" onClick={onBack}>返回修改</Button>
        </div>
      )}

      {status === "done" && persona && (
        <div className="ag-build-done">
          <Typography.Text>
            已生成「{persona.name}」· {persona.skeleton_name || persona.skeleton_id}
            {persona.status === "needs_review" && "（兜底产出，标记待复核）"}
          </Typography.Text>
          <Button type="primary" onClick={() => onDone(persona)}>进入专属页面</Button>
          <Button type="text" onClick={onBack}>返回修改</Button>
        </div>
      )}
    </div>
  );
}
