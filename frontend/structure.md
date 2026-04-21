# 前端目录结构说明

## 当前采用的结构

前端目录当前采用的是更贴近主流 React 项目的“按功能聚合 + 页面分层”结构，而不是把所有页面逻辑继续堆在 `App.tsx`。

```text
frontend/src
├─ app/
│  └─ App.tsx
├─ pages/
│  └─ auth/
│     └─ AuthPage.tsx
├─ features/
│  └─ auth/
│     ├─ api/
│     │  └─ authService.ts
│     ├─ lib/
│     │  └─ createNoticeFromError.ts
│     ├─ model/
│     │  ├─ constants.ts
│     │  └─ types.ts
│     └─ ui/
│        ├─ AuthCardHeader.tsx
│        ├─ AuthIcons.tsx
│        ├─ LoginForm.tsx
│        ├─ NoticeBanner.tsx
│        ├─ RegisterForm.tsx
│        └─ SignedInState.tsx
├─ shared/
│  └─ styles/
│     └─ global.css
├─ main.tsx
└─ vite-env.d.ts
```

## 为什么这样拆

这套结构适合 React + TypeScript + Vite 这类中小到中大型项目，原因是：

- `app/` 保持最薄，只处理应用启动、Provider 装配、路由容器这类全局职责。
- `pages/` 只处理“一个页面如何组装多个功能”，不会把可复用业务组件塞在页面里。
- `features/` 以业务功能聚合代码，当前是 `auth`，以后可以继续增加 `recipe`、`profile`、`dashboard` 等功能目录。
- `api`、`model`、`lib`、`ui` 这几层足够清晰，又不会像过重的架构那样让小项目变复杂。
- `shared/` 用来放跨页面共享的资源，当前先放全局样式，后续也可以放通用组件、hooks、工具函数。

## 当前约定

### 1. app 层

- `frontend/src/app/App.tsx` 只负责挂载页面，不承载复杂业务逻辑。

### 2. pages 层

- `frontend/src/pages/auth/AuthPage.tsx` 负责认证页面的状态管理、提交流程、模式切换和页面编排。
- 如果后续接入路由，每个页面都优先放在 `pages/` 下。

### 3. features 层

以 `auth` 为例：

- `api/`：封装接口请求和本地会话能力。
- `model/`：存放类型、常量、表单状态定义。
- `lib/`：存放和该功能相关但不属于 UI 的辅助逻辑。
- `ui/`：存放认证相关展示组件。

### 4. shared 层

- `shared/styles/global.css` 是全局样式入口。
- 后续如果出现跨功能复用组件，可以再新增 `shared/ui/`、`shared/lib/`、`shared/hooks/`。

## 后续新增页面时建议

- 新增路由页面时，先在 `pages/` 下建页面目录。
- 页面专属业务逻辑优先沉到对应 `features/`，不要直接堆进页面文件。
- 只有跨多个页面复用的内容，才进入 `shared/`。
- 不建议把所有接口重新集中回单一 `services/` 目录；优先按业务功能放到各自的 `features/*/api/` 中。
