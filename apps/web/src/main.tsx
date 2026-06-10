/*
 * main.tsx 是浏览器端挂载 React 应用的入口。
 * 后续无论页面怎么增加，通常只需要在这里保持全局样式和根组件挂载。
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
