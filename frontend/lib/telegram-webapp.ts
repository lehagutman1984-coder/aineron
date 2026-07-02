/**
 * S6 — обёртки Telegram Mini Apps 2.0 (Bot API 8.0+).
 *
 * Все функции безопасны на старых клиентах: проверяют наличие метода и
 * версию, при отсутствии — graceful no-op / фолбэк.
 */

export function getTg(): any | null {
  if (typeof window === "undefined") return null;
  return (window as any).Telegram?.WebApp ?? null;
}

function supports(method: string): boolean {
  const tg = getTg();
  return !!tg && typeof tg[method] === "function";
}

/** Инициализация: ready + expand; на мобильных — полноэкранный режим 2.0. */
export function initMiniApp(): void {
  const tg = getTg();
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    const platform = tg.platform ?? "";
    if (
      supports("requestFullscreen") &&
      (platform === "android" || platform === "ios")
    ) {
      tg.requestFullscreen();
    }
    if (supports("disableVerticalSwipes")) tg.disableVerticalSwipes();
  } catch {
    /* no-op */
  }
}

/** Промо «Добавить на главный экран» — иконка aineron на телефоне. */
export function promptAddToHomeScreen(): void {
  const tg = getTg();
  if (!tg) return;
  try {
    if (supports("checkHomeScreenStatus")) {
      tg.checkHomeScreenStatus((status: string) => {
        if (status === "missed" && supports("addToHomeScreen")) {
          tg.addToHomeScreen();
        }
      });
    } else if (supports("addToHomeScreen")) {
      tg.addToHomeScreen();
    }
  } catch {
    /* no-op */
  }
}

/** Поделиться подготовленным сообщением в любой чат (виральная петля). */
export function shareMessage(
  preparedMessageId: string,
  onDone?: (sent: boolean) => void
): boolean {
  const tg = getTg();
  if (!tg || !supports("shareMessage")) return false;
  try {
    tg.shareMessage(preparedMessageId, (sent: boolean) => onDone?.(sent));
    return true;
  } catch {
    return false;
  }
}

/** Картинка → стори пользователя с линком на бота. */
export function shareToStory(mediaUrl: string, botUsername: string): boolean {
  const tg = getTg();
  if (!tg || !supports("shareToStory")) return false;
  try {
    tg.shareToStory(mediaUrl, {
      widget_link: {
        url: `https://t.me/${botUsername}`,
        name: "aineron",
      },
    });
    return true;
  } catch {
    return false;
  }
}

/** Нативное скачивание файла (Bot API 8.0). Фолбэк — открыть ссылку. */
export function downloadFile(url: string, fileName: string): void {
  const tg = getTg();
  if (tg && supports("downloadFile")) {
    try {
      tg.downloadFile({ url, file_name: fileName });
      return;
    } catch {
      /* fallthrough */
    }
  }
  if (typeof window !== "undefined") window.open(url, "_blank");
}

/** Haptic feedback — лёгкий отклик на действия. */
export function haptic(style: "light" | "medium" | "success" = "light"): void {
  const tg = getTg();
  try {
    if (style === "success") tg?.HapticFeedback?.notificationOccurred("success");
    else tg?.HapticFeedback?.impactOccurred(style);
  } catch {
    /* no-op */
  }
}

// ─── SecureStorage для JWT (фолбэк — localStorage) ───

export function secureSet(key: string, value: string): void {
  const tg = getTg();
  const ss = tg?.SecureStorage;
  if (ss && typeof ss.setItem === "function") {
    try {
      ss.setItem(key, value, () => {});
      return;
    } catch {
      /* fallthrough */
    }
  }
  try {
    localStorage.setItem(key, value);
  } catch {
    /* no-op */
  }
}

export function secureGet(key: string): Promise<string | null> {
  return new Promise((resolve) => {
    const tg = getTg();
    const ss = tg?.SecureStorage;
    if (ss && typeof ss.getItem === "function") {
      try {
        ss.getItem(key, (err: unknown, value: string | null) => {
          if (!err && value) resolve(value);
          else resolve(localStorage.getItem(key));
        });
        return;
      } catch {
        /* fallthrough */
      }
    }
    try {
      resolve(localStorage.getItem(key));
    } catch {
      resolve(null);
    }
  });
}

// ─── DeviceStorage для черновиков ───

export function draftSave(key: string, value: string): void {
  const tg = getTg();
  const ds = tg?.DeviceStorage;
  if (ds && typeof ds.setItem === "function") {
    try {
      ds.setItem(key, value, () => {});
      return;
    } catch {
      /* fallthrough */
    }
  }
  try {
    localStorage.setItem(`draft:${key}`, value);
  } catch {
    /* no-op */
  }
}

export function draftLoad(key: string): Promise<string | null> {
  return new Promise((resolve) => {
    const tg = getTg();
    const ds = tg?.DeviceStorage;
    if (ds && typeof ds.getItem === "function") {
      try {
        ds.getItem(key, (err: unknown, value: string | null) => {
          resolve(!err && value ? value : localStorage.getItem(`draft:${key}`));
        });
        return;
      } catch {
        /* fallthrough */
      }
    }
    try {
      resolve(localStorage.getItem(`draft:${key}`));
    } catch {
      resolve(null);
    }
  });
}
