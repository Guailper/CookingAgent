/* 负责认证页背景中的装饰元素，让页面容器与表单内容分离。 */

export function AuthBackground() {
  return (
    <>
      <div className="backdrop-glow backdrop-glow--left" />
      <div className="backdrop-glow backdrop-glow--right" />
      <div className="backdrop-curve backdrop-curve--one" />
      <div className="backdrop-curve backdrop-curve--two" />
    </>
  );
}
