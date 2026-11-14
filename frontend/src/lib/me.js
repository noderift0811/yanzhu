// 当前账号的场景与语气：全局一份，避免每个页面各拉一次 /auth/me。
// 退出登录时调 resetMe()，否则换账号进来会先看到上一个人的场景。
import { useEffect, useState } from "react";
import { authStore, bootstrapAuth, request } from "./api.js";

let cache = null;
const listeners = new Set();

function publish(next) {
  cache = next;
  listeners.forEach((fn) => fn(next));
  return next;
}

export function getMe() {
  return cache;
}

export function resetMe() {
  publish(null);
}

export async function loadMe(force = false) {
  if (cache && !force) return cache;
  // 刷新页面后 access 只在内存里（已丢），必须先把 refresh 换成新的 access 再问 /auth/me，
  // 否则多个组件同时挂载会各发一条无令牌请求，401 触发刷新轮换把彼此挤掉、直接踢回登录页。
  if (!authStore.access && authStore.refresh) {
    await bootstrapAuth();
  }
  return publish(await request("/auth/me"));
}

// 只订阅，不自己发请求：加载由路由守卫统一负责。
// 早先这里在挂载且缓存为空时直接调 loadMe()，而守卫自己也在用它——冷启动时守卫
// 还没 bootstrapAuth 完，这个 effect 就抢先发了一条没有令牌的 /auth/me，控制台留 401。
export function useMe() {
  const [me, setMe] = useState(cache);
  useEffect(() => {
    const fn = (next) => setMe(next);
    listeners.add(fn);
    setMe(cache); // 首帧到 effect 之间可能已被守卫加载完，补一次同步
    return () => listeners.delete(fn);
  }, []);
  return me;
}

// 场景视图与 /auth/me 的字段是同构的，直接合并即可
export async function chooseScene(scene, confirm = false) {
  const data = await request("/auth/scene", { method: "POST", body: { scene, confirm } });
  publish({ ...(cache || {}), ...data });
  return data;
}

export async function patchTone(patch) {
  const data = await request("/auth/tone", { method: "PATCH", body: patch });
  publish({ ...(cache || {}), tone: data.tone });
  return data.tone;
}

// 「还有几天能换」这类文案不该由前端算时间：服务端给 next_switch_at，这里只做展示
export function formatSwitchAt(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso.slice(0, 10);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}
