import type { ReactNode } from "react";
import Link from "next/link";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        {children}
        <p className="mt-8 text-center text-[12px] text-[rgba(13,13,13,0.4)]">
          Продолжая, вы соглашаетесь с{" "}
          <Link href="/legal/terms/" className="hover:text-[#D97757] underline-offset-2 hover:underline">
            условиями
          </Link>{" "}
          и{" "}
          <Link href="/legal/privacy/" className="hover:text-[#D97757] underline-offset-2 hover:underline">
            политикой конфиденциальности
          </Link>
        </p>
      </div>
    </div>
  );
}
