"""
Статический scaffold UI-примитивов для V3. Записывается детерминированно
на шаге 0, чтобы не доверять качество базовых компонентов LLM.
Зависит только от Tailwind + lucide-react (без shadcn/radix).
"""

_BUTTON = """import { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const styles: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:opacity-90',
  secondary: 'bg-muted text-foreground hover:bg-muted/80',
  ghost: 'bg-transparent hover:bg-muted',
}

export function Button({ variant = 'primary', className = '', ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg h-10 px-4 text-sm font-medium transition disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}
"""

_CARD = """import { HTMLAttributes } from 'react'

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-xl border border-border bg-card p-6 shadow-sm ${className}`} {...props} />
  )
}
"""

_INPUT = """import { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-lg border border-border bg-background h-10 px-3 text-sm outline-none focus:ring-2 focus:ring-primary ${className}`}
      {...props}
    />
  )
}
"""

_BADGE = """import { HTMLAttributes } from 'react'

export function Badge({ className = '', ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={`inline-flex items-center rounded-md border border-border px-2 py-0.5 text-xs font-medium ${className}`} {...props} />
  )
}
"""


def scaffold_files(stack: str, design_md: str = '') -> dict:
    """
    Возвращает {path: content} стартовых UI-примитивов для react/nextjs.
    Для vue/html — пустой dict (примитивы не применяются).
    """
    if stack not in ('react', 'nextjs'):
        return {}
    base = 'src/components/ui'
    return {
        f'{base}/Button.tsx': _BUTTON,
        f'{base}/Card.tsx': _CARD,
        f'{base}/Input.tsx': _INPUT,
        f'{base}/Badge.tsx': _BADGE,
    }
