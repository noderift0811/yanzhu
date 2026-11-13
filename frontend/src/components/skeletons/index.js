import MinimalSkeleton from "./MinimalSkeleton.jsx";
import RadioSkeleton from "./RadioSkeleton.jsx";
import DiarySkeleton from "./DiarySkeleton.jsx";
import TerminalSkeleton from "./TerminalSkeleton.jsx";
import LetterSkeleton from "./LetterSkeleton.jsx";
import OracleSkeleton from "./OracleSkeleton.jsx";
import ClinicSkeleton from "./ClinicSkeleton.jsx";
import ReceiptSkeleton from "./ReceiptSkeleton.jsx";
import LibrarySkeleton from "./LibrarySkeleton.jsx";
import StarshipSkeleton from "./StarshipSkeleton.jsx";
import PotionSkeleton from "./PotionSkeleton.jsx";
import NeonSkeleton from "./NeonSkeleton.jsx";
import GardenSkeleton from "./GardenSkeleton.jsx";
import ClassroomSkeleton from "./ClassroomSkeleton.jsx";
import CasefileSkeleton from "./CasefileSkeleton.jsx";
import BbsSkeleton from "./BbsSkeleton.jsx";

// 16 套骨架。新增一套只需：写组件 + 在此登记 + 后端 SKELETONS 目录加一行。
const REGISTRY = {
  minimal: MinimalSkeleton,
  radio: RadioSkeleton,
  diary: DiarySkeleton,
  terminal: TerminalSkeleton,
  letter: LetterSkeleton,
  oracle: OracleSkeleton,
  clinic: ClinicSkeleton,
  receipt: ReceiptSkeleton,
  library: LibrarySkeleton,
  starship: StarshipSkeleton,
  potion: PotionSkeleton,
  neon: NeonSkeleton,
  garden: GardenSkeleton,
  classroom: ClassroomSkeleton,
  casefile: CasefileSkeleton,
  bbs: BbsSkeleton,
};

export function getSkeleton(id) {
  return REGISTRY[id] || MinimalSkeleton;
}

// 展示名：建造动画、聊天页副标、人格库卡片都读这里
export const SKELETON_NAMES = {
  minimal: "极简对话",
  radio: "深夜电台",
  diary: "手账书信",
  terminal: "终端风",
  letter: "素笺短札",
  oracle: "塔罗占卜",
  clinic: "门诊病历",
  receipt: "深夜小票",
  library: "借阅卡",
  starship: "星舰通讯",
  potion: "炼金配方",
  neon: "霓虹街",
  garden: "植物标本",
  classroom: "黑板课堂",
  casefile: "侦探卷宗",
  bbs: "复古论坛",
};

export const SKELETON_IDS = Object.keys(REGISTRY);
