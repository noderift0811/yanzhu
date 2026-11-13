// 主题微调用到的颜色算术与成套色板。零依赖、零外部资源。
//
// 为什么要有「成套色板」：五色里任何一个单独改都可能把对比度弄坏
//（比如把 text 调浅、bg 又调浅）。整套色板是预先算过对比度的组合，
// 用户点一下换的是「一套能看清的配色」，而不是随机撞色。

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function hexToRgb(hex) {
  const h = String(hex || "").replace("#", "").trim();
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

export function rgbToHex({ r, g, b }) {
  const p = (v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0");
  return `#${p(r)}${p(g)}${p(b)}`;
}

export function rgbToHsl({ r, g, b }) {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  const d = max - min;
  if (!d) return { h: 0, s: 0, l };
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === rn) h = ((gn - bn) / d + (gn < bn ? 6 : 0)) / 6;
  else if (max === gn) h = ((bn - rn) / d + 2) / 6;
  else h = ((rn - gn) / d + 4) / 6;
  return { h: h * 360, s, l };
}

export function hslToHex({ h, s, l }) {
  const hh = ((h % 360) + 360) % 360 / 360;
  const ss = clamp(s, 0, 1);
  const ll = clamp(l, 0, 1);
  if (!ss) {
    const v = Math.round(ll * 255);
    return rgbToHex({ r: v, g: v, b: v });
  }
  const q = ll < 0.5 ? ll * (1 + ss) : ll + ss - ll * ss;
  const p = 2 * ll - q;
  const hue = (t) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };
  return rgbToHex({
    r: hue(hh + 1 / 3) * 255,
    g: hue(hh) * 255,
    b: hue(hh - 1 / 3) * 255,
  });
}

// WCAG 相对亮度
export function luminance(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return 0;
  const ch = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(rgb.r) + 0.7152 * ch(rgb.g) + 0.0722 * ch(rgb.b);
}

// WCAG 对比度，1:1 ~ 21:1
export function contrast(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  const hi = Math.max(la, lb);
  const lo = Math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

// 对比度分级：正文与按钮文字都按 AA 正文标准 4.5
export function contrastGrade(ratio) {
  if (ratio >= 7) return { level: "AAA", tone: "good", text: "很清晰" };
  if (ratio >= 4.5) return { level: "AA", tone: "good", text: "清晰" };
  if (ratio >= 3) return { level: "AA-", tone: "warn", text: "偏淡" };
  return { level: "低", tone: "bad", text: "看不清" };
}

// 把某个颜色往远离底色的方向推，直到对比度达标（保色相与饱和，只动明度）
export function ensureContrast(hex, bg, target = 4.5) {
  if (contrast(hex, bg) >= target) return hex;
  const rgb = hexToRgb(hex);
  if (!rgb) return hex;
  const { h, s, l } = rgbToHsl(rgb);
  const step = luminance(bg) > 0.3 ? -0.015 : 0.015;
  let cur = l;
  for (let i = 0; i < 70; i += 1) {
    cur += step;
    if (cur <= 0.02 || cur >= 0.98) break;
    const cand = hslToHex({ h, s, l: cur });
    if (contrast(cand, bg) >= target) return cand;
  }
  return hex;
}

// 从主色派生一整套五色：底色取主色色相但极低饱和，避免页面被主色染成一团。
// mode: light（浅底深字）/ dark（深底浅字）
// 派生完会校正主色与点缀色，保证它们在派生出的底色上看得见。
export function derivePalette(primary, mode = "light") {
  const rgb = hexToRgb(primary);
  if (!rgb) return null;
  const { h, s } = rgbToHsl(rgb);
  const sat = clamp(s * 0.55, 0.08, 0.34);
  const accentRaw = hslToHex({ h: h + 32, s: clamp(s, 0.35, 0.85), l: mode === "dark" ? 0.63 : 0.46 });

  if (mode === "dark") {
    const bg = hslToHex({ h, s: sat * 0.5, l: 0.075 });
    const surface = hslToHex({ h, s: sat * 0.42, l: 0.12 });
    return {
      primary: ensureContrast(primary, bg, 4.5),
      bg,
      surface,
      text: hslToHex({ h, s: 0.1, l: 0.93 }),
      accent: ensureContrast(accentRaw, bg, 4.5),
    };
  }

  const bg = hslToHex({ h, s: sat * 0.42, l: 0.964 });
  const surface = hslToHex({ h, s: 0.3, l: 0.996 });
  return {
    primary: ensureContrast(primary, bg, 4.5),
    bg,
    surface,
    text: hslToHex({ h, s: 0.14, l: 0.16 }),
    accent: ensureContrast(accentRaw, bg, 3.2),
  };
}

// 判断当前主题偏深还是偏浅（按底色亮度）
export function isDarkTheme(theme) {
  return luminance(theme?.bg || "#ffffff") < 0.35;
}

// 某个底色上该用深字还是浅字（按钮、用户气泡用）：两种都算一遍取更清楚的那个
export function readableOn(bg) {
  return contrast(bg, "#ffffff") >= contrast(bg, "#12161c") ? "#ffffff" : "#12161c";
}

// 某套骨架的底色是不是「固定的」。
// 这些骨架的底色是它的固有印记（霓虹的黑、黑板的墨绿、牛皮纸的米黄），
// 写在样式里而不是吃 --pf-bg，所以换浅色配色看不出变化。
// 面板据此把配色自动配平到同明暗方向，避免「点了没反应」。
export const SKELETON_TONE = {
  oracle: "dark",
  receipt: "dark",
  starship: "dark",
  neon: "dark",
  classroom: "dark",
  casefile: "light",
  bbs: "light",
};

export function skeletonTone(skeletonId) {
  return SKELETON_TONE[skeletonId] || "auto";
}

// 12 套成套色板：每套都是算过对比度的组合，点击即整套替换。
// bg / surface 明暗成对，text 与 bg 的对比度都在 9:1 以上。
export const THEME_PRESETS = [
  {
    id: "ink",
    name: "纸墨",
    theme: {
      primary: "#4f46e5", bg: "#f7f7f8", surface: "#ffffff", text: "#1f2328", accent: "#7c6cf0",
      font_style: "system", decoration: "none",
    },
  },
  {
    id: "oldpaper",
    name: "旧纸",
    theme: {
      primary: "#8a6a3a", bg: "#f6efe2", surface: "#fffdf6", text: "#3a2f22", accent: "#ab7f48",
      font_style: "serif", decoration: "paper",
    },
  },
  {
    id: "moss",
    name: "苔绿",
    theme: {
      primary: "#5e7a4a", bg: "#f2f4ec", surface: "#fbfcf5", text: "#2f3a2a", accent: "#749452",
      font_style: "serif", decoration: "none",
    },
  },
  {
    id: "seafog",
    name: "海雾",
    theme: {
      primary: "#2f6fb3", bg: "#eff4f9", surface: "#ffffff", text: "#1f2d3d", accent: "#5591c0",
      font_style: "system", decoration: "none",
    },
  },
  {
    id: "dusk",
    name: "暮紫",
    theme: {
      primary: "#7c5cff", bg: "#f5f3fc", surface: "#ffffff", text: "#241f33", accent: "#b48341",
      font_style: "rounded", decoration: "stars",
    },
  },
  {
    id: "cream",
    name: "奶油",
    theme: {
      primary: "#c28337", bg: "#fdf8ef", surface: "#fffdf7", text: "#3a3025", accent: "#bf8128",
      font_style: "rounded", decoration: "petal",
    },
  },
  {
    id: "wine",
    name: "酒红",
    theme: {
      primary: "#9b2c3a", bg: "#fbf4f3", surface: "#fffdfd", text: "#2e1a1a", accent: "#c77665",
      font_style: "serif", decoration: "paper",
    },
  },
  {
    id: "sky",
    name: "天青",
    theme: {
      primary: "#0e7490", bg: "#eefafb", surface: "#ffffff", text: "#12343b", accent: "#3a9bac",
      font_style: "system", decoration: "grid",
    },
  },
  {
    id: "charcoal",
    name: "炭黑",
    theme: {
      primary: "#e8e4d0", bg: "#14161a", surface: "#1e2126", text: "#f0f2f5", accent: "#9aa4b2",
      font_style: "mono", decoration: "none",
    },
  },
  {
    id: "midnight",
    name: "夜蓝",
    theme: {
      primary: "#38bdf8", bg: "#0a1220", surface: "#12203a", text: "#d6e4f5", accent: "#7dd3fc",
      font_style: "mono", decoration: "stars",
    },
  },
  {
    id: "neonnight",
    name: "霓虹",
    theme: {
      primary: "#ff2d95", bg: "#0a0a10", surface: "#16101e", text: "#f4eeff", accent: "#22d3ee",
      font_style: "mono", decoration: "grid",
    },
  },
  {
    id: "blackboard",
    name: "墨绿",
    theme: {
      primary: "#3b8666", bg: "#123027", surface: "#1b3d32", text: "#eaf3ee", accent: "#a8d5b5",
      font_style: "serif", decoration: "none",
    },
  },
];

export const COLOR_FIELDS = [  { key: "primary", label: "主色", hint: "按钮、强调、光标" },
  { key: "accent", label: "点缀色", hint: "分隔线、标签、装饰" },
  { key: "bg", label: "背景", hint: "页面底色" },
  { key: "surface", label: "卡片", hint: "气泡与面板底" },
  { key: "text", label: "文字", hint: "正文颜色" },
];

export const FONT_OPTIONS = [
  { value: "system", label: "系统", sample: "Aa 清朗" },
  { value: "rounded", label: "圆润", sample: "Aa 柔和" },
  { value: "serif", label: "衬线", sample: "Aa 书卷" },
  { value: "mono", label: "等宽", sample: "Aa 机械" },
];

export const DECOR_OPTIONS = [
  { value: "none", label: "无" },
  { value: "paper", label: "纸纹" },
  { value: "petal", label: "花瓣" },
  { value: "stars", label: "星点" },
  { value: "grid", label: "网格" },
];
