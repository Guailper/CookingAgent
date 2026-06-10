import {
  createContext,
  use,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import { tokenStorage } from "@/lib/auth/token-storage";
import type { UserProfile } from "@/types/api";

import { getCurrentUser, loginWithPassword, type PasswordLoginInput } from "../services/auth-service";

type AuthStatus = "loading" | "guest" | "authenticated";

type AuthContextValue = {
  status: AuthStatus;
  user: UserProfile | null;
  signIn: (input: PasswordLoginInput) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const token = await tokenStorage.get();
      if (!token) {
        if (!cancelled) setStatus("guest");
        return;
      }

      try {
        const currentUser = await getCurrentUser();
        if (!cancelled) {
          setUser(currentUser);
          setStatus("authenticated");
        }
      } catch {
        await tokenStorage.remove();
        if (!cancelled) setStatus("guest");
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      signIn: async (input) => {
        const payload = await loginWithPassword(input);
        await tokenStorage.set(payload.access_token);
        setUser(payload.user);
        setStatus("authenticated");
      },
      signOut: async () => {
        await tokenStorage.remove();
        setUser(null);
        setStatus("guest");
      },
    }),
    [status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = use(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
