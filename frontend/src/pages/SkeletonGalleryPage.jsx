import { SKELETON_IDS, SKELETON_NAMES, getSkeleton } from "../components/skeletons/index.js";
import { useThemeVars } from "../hooks/useThemeVars.js";
import "../styles/gallery.css";

// 骨架画廊：内部验收页，只在开发模式注册（见 App.jsx）。
// 用固定 mock 数据把 16 套骨架并排渲染，用来比对视觉差异、检查溢出，不依赖后端与 LLM。

const T = "2026-10-26T14:02:33";

const MESSAGES = [
  {
    id: "m1",
    role: "assistant",
    created_at: T,
    content:
      "你来得正好。水刚烧开，茶叶还没放下去。先坐着吧，不用急着说什么——沉默在这里也算一种回答。",
  },
  {
    id: "m2",
    role: "user",
    created_at: T,
    content: "我最近总是睡不好，一闭眼就想起白天说错的话。",
  },
  {
    id: "m3",
    role: "assistant",
    created_at: T,
    content:
      "说错的话不会因为你去想它就变对，但它会提醒你下次慢一点。今晚先别复盘了，明天再说。",
  },
];

const DEMO_SPEC = {
  name: "小笺",
  page_copy: {
    title: "小笺的信",
    greeting: "我在，慢慢说。",
    input_placeholder: "写给我一句话…",
  },
  theme: {
    primary: "#7c5cff",
    bg: "#f7f6f3",
    surface: "#ffffff",
    text: "#24232b",
    accent: "#b08d57",
    font_style: "serif",
    decoration: "none",
  },
};

function GalleryItem({ id }) {
  const Skeleton = getSkeleton(id);
  const { style, className } = useThemeVars(DEMO_SPEC.theme);
  const persona = {
    id: "demo-0001",
    name: DEMO_SPEC.name,
    status: "active",
    spec: { ...DEMO_SPEC, skeleton_id: id },
  };

  return (
    <section className="gal-item" id={`sk-${id}`}>
      <header className="gal-head">
        <h2>
          {SKELETON_NAMES[id]} <code>{id}</code>
        </h2>
      </header>
      <div className={`pf-chat gal-chat ${className}`} style={style}>
        <Skeleton persona={persona} messages={MESSAGES} sending={false} error={null} onSend={() => {}} />
      </div>
    </section>
  );
}

export default function SkeletonGalleryPage() {
  return (
    <div className="gal-page">
      <header className="gal-page-head">
        <h1>言筑 · 骨架画廊</h1>
        <p>
          共 {SKELETON_IDS.length} 套。同一份 mock 对话、同一套主题 token，只换骨架 id。开发模式专用。
        </p>
      </header>
      <div className="gal-list">
        {SKELETON_IDS.map((id) => (
          <GalleryItem key={id} id={id} />
        ))}
      </div>
    </div>
  );
}
