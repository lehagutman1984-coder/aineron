import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

/**
 * Locale-aware навигация (GLOBAL_EXPANSION_PLAN.md, G4).
 * Использовать ВЕЗДЕ вместо next/link и next/navigation — иначе переход
 * по plain <Link href="/models/"> у fa/tr-пользователя молча сбросит
 * его на дефолтную локаль (потеряет префикс /fa/, /tr/...).
 */
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
