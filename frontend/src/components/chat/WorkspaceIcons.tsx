/*
 * 主界面图标统一放在这里，方便后续做风格统一替换。
 * 这样页面和组件文件不会堆太多 SVG 细节。
 */

export function PanelToggleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 6.5h16" />
      <path d="M4 12h16" />
      <path d="M4 17.5h10" />
    </svg>
  );
}

export function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="10.5" cy="10.5" r="5.5" />
      <path d="m15 15 4 4" />
    </svg>
  );
}

export function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 18h8" />
      <path d="M10 20a2 2 0 0 0 4 0" />
      <path d="M6 17V11a6 6 0 0 1 12 0v6" />
    </svg>
  );
}

export function HelpIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.8 9.5a2.5 2.5 0 1 1 4.2 2c-.9.7-2 1.3-2 2.5" />
      <path d="M12 17.3h.01" />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 8v4.5l3 1.8" />
    </svg>
  );
}

export function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 4 1.5 3.5L17 9l-3.5 1.5L12 14l-1.5-3.5L7 9l3.5-1.5Z" />
      <path d="m18.5 15 1 2.2L21.8 18l-2.3.8-1 2.2-1-2.2-2.3-.8 2.3-.8Z" />
    </svg>
  );
}

export function PanIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 14h8.5a3.5 3.5 0 1 0 0-7H6" />
      <path d="M6 10h10" />
      <path d="M17 10h2.5" />
      <path d="M5 14v2.5a2.5 2.5 0 0 0 2.5 2.5H14" />
    </svg>
  );
}

export function LeafIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18.5 5.5c-5.8 0-10 3.5-10 8.8 0 2.5 1.9 4.2 4.6 4.2 4.3 0 6.9-4.2 6.9-8.4 0-1.3-.3-3-.9-4.6Z" />
      <path d="M8.7 18.2c1.6-2 4.2-4.5 7.8-6.6" />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 5 0 14" />
      <path d="m6.5 10.5 5.5-5.5 5.5 5.5" />
    </svg>
  );
}

export function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 4 1.4 1.6 2.1-.1.7 2 1.9.8-.4 2.1 1.3 1.6-1.3 1.6.4 2.1-1.9.8-.7 2-2.1-.1L12 20l-1.4-1.6-2.1.1-.7-2-1.9-.8.4-2.1L5 12l1.3-1.6-.4-2.1 1.9-.8.7-2 2.1.1Z" />
      <circle cx="12" cy="12" r="2.8" />
    </svg>
  );
}
