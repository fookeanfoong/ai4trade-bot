/**
 * Small shared UI primitives. Kept in one file to avoid sprawl.
 * Colours follow the design spec: green/red are semantic only.
 */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger';
}) {
  const base =
    'w-full rounded-card px-4 py-3 text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed';
  const variants: Record<string, string> = {
    primary: 'bg-accent text-white hover:bg-accent/90',
    ghost: 'bg-transparent border border-border text-text hover:bg-surface',
    danger: 'bg-transparent border border-bear/60 text-bear hover:bg-bear/10',
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function TextInput({
  label,
  hint,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string; error?: string }) {
  return (
    <label className="block">
      {label && <span className="mb-1 block text-sm text-muted">{label}</span>}
      <input
        className="w-full rounded-card border border-border bg-card px-3 py-3 text-text outline-none focus:border-accent"
        {...props}
      />
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-bear">{error}</span>}
    </label>
  );
}

/** Accessible checkbox row with rich (link-bearing) label content. */
export function Checkbox({
  checked,
  onChange,
  children,
  id,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
  id: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-5 w-5 shrink-0 accent-accent"
      />
      <label htmlFor={id} className="text-sm leading-relaxed text-text">
        {children}
      </label>
    </div>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-card border border-border bg-card p-4 ${className}`}>{children}</div>
  );
}

export function Screen({
  children,
  title,
  className = '',
}: {
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <div className={`flex min-h-full flex-col ${className}`}>
      {title && (
        <header className="pt-safe sticky top-0 z-10 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur">
          <h1 className="text-lg font-bold">{title}</h1>
        </header>
      )}
      <div className="flex-1">{children}</div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-accent" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
