import { getSkeleton } from "./skeletons/index.js";
import { useThemeVars } from "../hooks/useThemeVars.js";
import "../styles/persona-preview.css";

// 预览用的三句样例对话：足够让骨架的消息区 / 输入区摆出真实排版，
// 又不至于在小图里挤成一团。内容刻意中性，不与任何场景绑定。
const MOCK_MESSAGES = [
  { id: "pv-a1", role: "assistant", content: "你来得正好，先坐吧。" },
  { id: "pv-u1", role: "user", content: "今天有点累。" },
  { id: "pv-a2", role: "assistant", content: "那就慢慢说，我听着。" },
];

// 人格库卡片的界面预览：直接渲染这套骨架本体 + 这个人格的配色 token，
// 不用截图不用图片资源——骨架怎么变，缩略图就跟着怎么变。
// 整体 pointer-events 关掉、压到 0.42 缩放，纯展示。
export default function PersonaPreview({ persona }) {
  // 列表接口只回 summary（theme / skeleton_id），详情页才带 spec.theme
  const theme = persona?.spec?.theme || persona?.theme || null;
  const { style, className } = useThemeVars(theme);
  const Skeleton = getSkeleton(persona?.skeleton_id);

  return (
    <div className={`pv-frame ${className}`} style={style} aria-hidden="true">
      <div className="pv-stage">
        <Skeleton
          persona={persona}
          messages={MOCK_MESSAGES}
          sending={false}
          error=""
          onSend={() => {}}
        />
      </div>
      <span className="pv-tag">界面预览</span>
    </div>
  );
}
