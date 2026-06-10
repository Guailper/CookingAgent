# CookingAgent Android

Expo Router + React Native Android client for the existing CookingAgent FastAPI backend.

## Local setup

```powershell
cd apps/android
Copy-Item .env.example .env.local
npm install
npm start
```

For a physical Android device, set `EXPO_PUBLIC_API_URL` to the computer's LAN address:

```env
EXPO_PUBLIC_API_URL=http://192.168.31.254:8000/api/v1
```

Start the backend on the LAN:

```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Commands

```powershell
npm test
npm run typecheck
npm run lint
npm run android
```

## Structure

```text
src/
  app/          Expo Router routes
  components/   Shared UI components
  constants/    Theme and app constants
  features/     Auth, chat, attachment, and future voice features
  lib/          API, SSE, and secure token infrastructure
  providers/    Application-level providers
  types/        Backend API contracts
```

The initial scaffold supports password login, secure token storage, conversation listing and
creation, message history, and streaming Agent responses. Attachment picking is prepared under
`src/features/attachments`; upload and voice composer UI can be added incrementally.
