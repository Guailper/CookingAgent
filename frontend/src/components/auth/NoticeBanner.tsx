/* 用来展示成功、失败、提示等状态消息。 */

import type { Notice } from "../../types";

type NoticeBannerProps = {
  notice: Notice;
};

export function NoticeBanner({ notice }: NoticeBannerProps) {
  return (
    <div className={`notice notice--${notice.tone}`} role="status" aria-live="polite">
      <strong>{notice.title}</strong>
      <span>{notice.description}</span>
    </div>
  );
}
