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
        // Гонка: этот запрос ушёл ещё анонимным при монтировании layout'а и
        // всегда резолвится 401 независимо от того, что произошло позже —
        // куки в уже отправленном запросе не обновляются задним числом.
        // Если пользователь успел зарегистрироваться/войти, пока этот запрос
        // летел, setUser(null) здесь затирал бы свежую сессию до перезагрузки
        // страницы (баг: после регистрации кабинет требовал войти заново).
        if (!useAuthStore.getState().user) {
          setUser(null);
        }
        setLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
