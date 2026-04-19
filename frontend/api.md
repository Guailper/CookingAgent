# 前后端对接说明

## 目录约定

- `frontend/`：前端界面、页面逻辑、样式、前端服务层。
- `backend/`：后端代码。
- `FRONTEND_BACKEND_INTEGRATION.md`：所有界面的前后端对接说明统一写在这个文件里，后续新增界面继续追加。

## 当前界面 1：登录 / 注册页

### 前端文件位置

- 页面主文件：`frontend/src/App.tsx`
- 前端接口适配层：`frontend/src/services/authService.ts`

### 当前实现方式

- 当前 `authService.ts` 还是 demo 实现，暂时使用浏览器 `localStorage` 模拟后端。
- 真正接后端时，不要在 `App.tsx` 里直接写 `fetch`。
- 只需要把 `frontend/src/services/authService.ts` 里的 `login`、`registerAccount`、`requestPasswordReset` 改成真实接口请求即可。

### 建议后端接口

#### 1. 注册接口

- 方法：`POST /api/auth/register`
- 前端调用函数：`registerAccount`

请求体：

```json
{
  "fullName": "Alex Morgan",
  "email": "name@company.com",
  "password": "12345678",
  "confirmPassword": "12345678"
}
```

成功响应建议：

```json
{
  "user": {
    "id": "u_001",
    "fullName": "Alex Morgan",
    "email": "name@company.com",
    "createdAt": "2026-04-18T12:00:00.000Z"
  }
}
```

前端成功后的处理：

- 切换回登录页
- 自动把刚注册的 `email` 和 `password` 回填到登录框
- 当前页面设计是不直接登录

#### 2. 登录接口

- 方法：`POST /api/auth/login`
- 前端调用函数：`login`

请求体：

```json
{
  "email": "name@company.com",
  "password": "12345678"
}
```

成功响应最少需要：

```json
{
  "user": {
    "id": "u_001",
    "fullName": "Alex Morgan",
    "email": "name@company.com",
    "createdAt": "2026-04-18T12:00:00.000Z"
  }
}
```

如果你使用 JWT，可以额外返回：

```json
{
  "user": {
    "id": "u_001",
    "fullName": "Alex Morgan",
    "email": "name@company.com",
    "createdAt": "2026-04-18T12:00:00.000Z"
  },
  "token": "jwt-token"
}
```

前端成功后的处理：

- 页面进入已登录状态
- 后续可以在这里继续跳转到 dashboard 页面

补充说明：

- 当前页面里的 `remember` 选项是“是否在当前浏览器记住密码”，这是前端本地行为。
- 如果后端以后也要支持“记住登录状态”，可以额外在登录接口里增加 `rememberMe` 字段。

#### 3. 忘记密码接口

- 方法：`POST /api/auth/forgot-password`
- 前端调用函数：`requestPasswordReset`

请求体：

```json
{
  "email": "name@company.com"
}
```

成功响应建议：

```json
{
  "message": "Reset email sent"
}
```

当前前端行为：

- 现在这个按钮已经预留了调用点
- 真接后端时，只改 `requestPasswordReset` 即可

### 错误响应建议

建议后端统一返回这个格式：

```json
{
  "code": "EMAIL_EXISTS",
  "message": "Email is already registered"
}
```

这样前端服务层可以统一把错误转成页面提示。

### 后端代码放置建议

- 具体的 HTTP 接口代码放在 `backend/` 下面。
- 例如你后续如果用 Python Web 框架，可以把鉴权相关接口集中放在 `backend/auth/`、`backend/routes/` 或你框架默认的路由目录中。

## 后续新增界面时的追加模板

复制下面这段，继续追加到本文件：

````md
## 当前界面 X：界面名称

### 前端文件位置
- 页面主文件：
- 前端接口适配层：

### 功能说明
- 

### 需要的后端接口
#### 1. 接口名称
- 方法：
- 路径：
- 前端调用函数：

请求体：
```json
{}
```

成功响应：
```json
{}
```

前端成功后的处理：
- 

### 错误响应建议
```json
{
  "code": "",
  "message": ""
}
```
````
