import Script from 'next/script'
import type { ReactNode } from 'react'

export default function TgLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <Script
        src="https://telegram.org/js/telegram-web-app.js"
        strategy="beforeInteractive"
      />
      {children}
    </>
  )
}
