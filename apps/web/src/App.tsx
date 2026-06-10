/*
 * App 现在只负责承接应用的最外层入口。
 * 真正的页面组织交给 router，具体界面逻辑交给 pages / hooks / components。
 */

import AppRouter from "./router";

export default function App() {
  return <AppRouter />;
}
