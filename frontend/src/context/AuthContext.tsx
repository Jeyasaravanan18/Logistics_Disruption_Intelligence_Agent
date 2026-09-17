"use client";
import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchMe, loginApi, logoutApi } from "@/lib/api";

interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
  accessToken: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const restore = async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        if (res.ok) {
          const tokens = await res.json();
          if (tokens.access_token) {
            setAccessToken(tokens.access_token);
            sessionStorage.setItem("ws_token", tokens.access_token);
          }
          const profile = await fetchMe();
          setUser(profile);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    restore();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginApi(email, password);
    setAccessToken(tokens.access_token || null);
    if (typeof window !== "undefined") {
      sessionStorage.setItem("ws_token", tokens.access_token);
    }
    const profile = await fetchMe();
    setUser(profile);
    router.push("/");
  }, [router]);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      /* ignore */
    }
    setUser(null);
    setAccessToken(null);
    sessionStorage.removeItem("ws_token");
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading, accessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
