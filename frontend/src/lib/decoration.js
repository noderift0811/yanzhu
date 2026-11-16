// 装修台桥接：悬浮球（App 全局层）与聊天页（路由层）之间的轻量通道。
//
// 为什么需要它：AssistantFab 挂在 Guard 里、脱离路由，拿不到当前人格，也不知道
// ThemePanel / SkeletonPicker 的 open 状态（那两个面板的 open 由 ChatView 持有）。
// 直接把面板搬进悬浮球会重复一套预览/保存逻辑，还容易和聊天页的实时预览打架。
// 所以这里只传「能不能装修 + 打开哪个面板」两件事，面板本体仍由聊天页渲染，
// 预览通道（onPreview → draftTheme）和保存回写（onSaved → setCurrent）原样复用。
//
// 风格与 me.js 一致：模块级单例 + 发布订阅，避免给整棵树再套一层 Context。
import { useEffect, useState } from "react";

let state = null;
const listeners = new Set();

function publish(next) {
  state = next;
  listeners.forEach((fn) => fn(next));
}

// 聊天页调用：登记当前人格、面板打开函数，以及 AI 装修的预览/保存通道。返回卸载清理函数。
// handle = { persona, skeletonName, openTheme(), openSkeleton(),
//            previewTheme(theme), resetPreview(), applyTheme(theme) }
// AI 装修：悬浮球拿到 AI 产出的 theme → previewTheme 实时套用 → 用户点「采用」才 applyTheme 落库。
export function registerDecoration(handle) {
  publish(handle);
  return () => {
    if (state === handle) publish(null);
  };
}

// 悬浮球读取是否处于可装修页面（聊天页）。
// 返回的 handle 自带 openTheme()/openSkeleton()，悬浮球就地调用即可，
// 面板本体仍由聊天页渲染，预览/保存逻辑完全复用。
export function useDecoration() {
  const [v, setV] = useState(state);
  useEffect(() => {
    const fn = (next) => setV(next);
    listeners.add(fn);
    setV(state); // 挂载时补一次同步，防止首帧与 effect 之间已登记完
    return () => listeners.delete(fn);
  }, []);
  return v;
}
