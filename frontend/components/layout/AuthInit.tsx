"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/auth";
import { getMe } from "@/lib/api/client";

// Bootstraps auth state on app mount by hitting the DRF /auth/me/ endpoint.
// Returns null so it renders nothing; lives in the root layout.
export function AuthInit() {
  const { setUser, setLoading } = useAuthStore();

  useEffect(() => {
    setLoading(true);
    getMe()
      .then((u) => setUser(u))
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
