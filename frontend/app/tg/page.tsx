'use client'

import { useEffect, useState } from 'react'

interface UserInfo {
  id: number
  email: string
  pages_count: number
}

const linkStyle: React.CSSProperties = {
  display: 'block',
  padding: '14px 16px',
  background: 'var(--tg-theme-button-color, #C4623E)',
  color: 'var(--tg-theme-button-text-color, #fff)',
  borderRadius: 10,
  textDecoration: 'none',
  fontWeight: 600,
  fontSize: 15,
  textAlign: 'center',
}

export default function TelegramMiniApp() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp
    if (tg) {
      tg.ready()
      tg.expand()
    }

    const initData = tg?.initData || ''
    if (!initData) {
      setError('Открой через Telegram-бот (@aineron_bot)')
      setLoading(false)
      return
    }

    fetch('/api/v1/telegram/webapp-auth/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: initData }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.access) {
          localStorage.setItem('access_token', data.access)
          if (data.refresh) localStorage.setItem('refresh_token', data.refresh)
          setUser(data.user)
        } else {
          setError(data.error || 'Ошибка авторизации')
        }
        setLoading(false)
      })
      .catch(() => {
        setError('Ошибка сети')
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div style={{ padding: 32, textAlign: 'center', fontFamily: 'system-ui' }}>
        Загрузка...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 24, fontFamily: 'system-ui' }}>
        <p style={{ color: 'red' }}>{error}</p>
        <p style={{ fontSize: 14, color: '#666' }}>
          Привяжи аккаунт: напиши /start боту и следуй инструкциям.
        </p>
      </div>
    )
  }

  return (
    <div
      style={{
        padding: 16,
        fontFamily: 'system-ui',
        maxWidth: 480,
        margin: '0 auto',
        background: 'var(--tg-theme-bg-color, #fff)',
        color: 'var(--tg-theme-text-color, #000)',
        minHeight: '100vh',
      }}
    >
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>aineron.ru</h2>

      {user && (
        <div
          style={{
            background: 'var(--tg-theme-secondary-bg-color, #f5f5f5)',
            borderRadius: 12,
            padding: 16,
            marginBottom: 20,
          }}
        >
          <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color, #666)', marginBottom: 4 }}>
            Баланс
          </div>
          <div style={{ fontSize: 32, fontWeight: 700 }}>{user.pages_count}</div>
          <div style={{ fontSize: 14, color: 'var(--tg-theme-hint-color, #666)' }}>звёзд</div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <a href="/account/billing/" style={linkStyle}>
          Пополнить баланс
        </a>
        <a href="/account/analytics/" style={linkStyle}>
          Аналитика трат
        </a>
        <a href="/account/referral/" style={linkStyle}>
          Реферальная программа
        </a>
        <a href="/models/" style={linkStyle}>
          Каталог AI-моделей
        </a>
        <a href="/chat/" style={linkStyle}>
          Чат с AI
        </a>
      </div>

      {user && (
        <p
          style={{
            marginTop: 20,
            fontSize: 12,
            color: 'var(--tg-theme-hint-color, #999)',
            textAlign: 'center',
          }}
        >
          {user.email}
        </p>
      )}
    </div>
  )
}
