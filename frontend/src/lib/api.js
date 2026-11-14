// API 封装：fetch + JWT（access 内存 / refresh localStorage）+ 401 静默刷新重试一次
const REFRESH_KEY = "pf_refresh_token";
let accessToken = null;
let refreshToken = localStorage.getItem(REFRESH_KEY);

export class ApiError extends Error {
  constructor(status, code, message, extra = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.message = message;
    this.extra = extra;
  }
}

export const authStore = {
  get access() {
    return accessToken;
  },
  get refresh() {
    return refreshToken;
  },
  setTokens(access, refresh) {
    accessToken = access || null;
    if (refresh) {
      refreshToken = refresh;
      localStorage.setItem(REFRESH_KEY, refresh);
    }
  },
  clear() {
    accessToken = null;
    refreshToken = null;
    localStorage.removeItem(REFRESH_KEY);
  },
};

// 令牌走自定义头而不是 Authorization：公网分享时隧道会挂 HTTP Basic 认证，
// Basic 与 Bearer 共用 Authorization 会互相挤掉，导致所有接口 401。
const TOKEN_HEADER = "X-Yanzhu-Token";

async function raw(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && accessToken) headers[TOKEN_HEADER] = accessToken;
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* 非 JSON 响应 */
  }
  if (!res.ok) {
    throw new ApiError(res.status, data.code || "HTTP_ERROR", data.message || `请求失败(${res.status})`, data);
  }
  return data;
}

let refreshInFlight = null;

async function tryRefresh() {
  if (!refreshToken) return false;
  // 并发 401 共享同一次刷新：refresh 是轮换制，重复刷新会把彼此作废、误踢下线
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const data = await raw("/auth/refresh", { method: "POST", body: { refresh_token: refreshToken }, auth: false });
      authStore.setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      authStore.clear();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function request(path, opts = {}, retried = false) {
  // 冷启动（刚刷新页面）时 access 只在内存里、已经丢了：先换一次再发，
  // 否则每条请求都要先吃一个 401 再重试——浏览器控制台会记一堆红色错误，
  // 多个请求同时 401 时还可能把刷新令牌的轮换挤掉。
  if (opts.auth !== false && !accessToken && refreshToken) {
    await tryRefresh();
  }
  try {
    return await raw(path, opts);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && opts.auth !== false && !retried) {
      if (await tryRefresh()) return request(path, opts, true);
      authStore.clear();
      if (!location.hash.startsWith("#/login")) location.hash = "#/login";
    }
    throw e;
  }
}

// SSE 流式请求：POST + fetch ReadableStream（EventSource 只支持 GET）。
// onEvent(event, data) 逐事件回调；HTTP 层错误（含 401 刷新重试一次）抛 ApiError。
export async function streamSSE(path, { method = "POST", body, onEvent }) {
  if (!accessToken && refreshToken) await tryRefresh();
  const doFetch = async (retried) => {
    const headers = { "Content-Type": "application/json" };
    if (authStore.access) headers[TOKEN_HEADER] = authStore.access;
    const res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (res.status === 401 && !retried) {
      if (await tryRefresh()) return doFetch(true);
      authStore.clear();
      if (!location.hash.startsWith("#/login")) location.hash = "#/login";
    }
    return res;
  };

  const res = await doFetch(false);
  if (!res.ok) {
    let data = {};
    try {
      data = await res.json();
    } catch {
      /* 非 JSON 响应 */
    }
    throw new ApiError(res.status, data.code || "HTTP_ERROR", data.message || `请求失败(${res.status})`, data);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      try {
        onEvent(event, JSON.parse(dataLines.join("\n")));
      } catch {
        /* 忽略无法解析的事件 */
      }
    }
  }
}

export async function bootstrapAuth() {
  if (!authStore.refresh) {
    authStore.clear();
    return false;
  }
  return tryRefresh();
}
