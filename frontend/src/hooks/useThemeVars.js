// theme token → CSS 自定义属性；零图片、零外部字体，全部系统字体栈
const FONT_STACKS = {
  rounded: '"Yuanti SC","YouYuan","PingFang SC","Microsoft YaHei",sans-serif',
  serif: 'Georgia,"Songti SC","SimSun",serif',
  mono: '"Cascadia Code","JetBrains Mono",Consolas,"Courier New",monospace',
  system: '-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif',
};

export function useThemeVars(theme) {
  if (!theme) return { style: {}, className: "pf-deco-none" };
  const style = {
    "--pf-primary": theme.primary,
    "--pf-bg": theme.bg,
    "--pf-surface": theme.surface,
    "--pf-text": theme.text,
    "--pf-accent": theme.accent,
    "--pf-font": FONT_STACKS[theme.font_style] || FONT_STACKS.system,
  };
  return { style, className: `pf-deco-${theme.decoration || "none"}` };
}
