/**
 * Bottom tab navigation: Signals / News / Learn / Account.
 * Icons are inline SVG so there's no external icon dependency.
 */
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';

function Tab({ to, label, icon }: { to: string; label: string; icon: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex flex-1 flex-col items-center gap-1 py-2 text-[11px] ${
          isActive ? 'text-text' : 'text-muted'
        }`
      }
    >
      {icon}
      <span>{label}</span>
    </NavLink>
  );
}

const iconProps = {
  width: 22,
  height: 22,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export default function TabBar() {
  const { t } = useTranslation();
  return (
    <nav className="pb-safe flex border-t border-border bg-surface">
      <Tab
        to="/signals"
        label={t('common.signals')}
        icon={
          <svg {...iconProps}>
            <path d="M3 17l6-6 4 4 8-8" />
            <path d="M21 7v6" />
          </svg>
        }
      />
      <Tab
        to="/news"
        label={t('common.news')}
        icon={
          <svg {...iconProps}>
            <path d="M4 4h13v16H6a2 2 0 0 1-2-2V4z" />
            <path d="M17 8h3v10a2 2 0 0 1-2 2" />
            <path d="M8 8h6M8 12h6M8 16h4" />
          </svg>
        }
      />
      <Tab
        to="/learn"
        label={t('common.learn')}
        icon={
          <svg {...iconProps}>
            <path d="M4 5a2 2 0 0 1 2-2h9v16H6a2 2 0 0 0-2 2V5z" />
            <path d="M15 3h3a1 1 0 0 1 1 1v15" />
          </svg>
        }
      />
      <Tab
        to="/account"
        label={t('common.account')}
        icon={
          <svg {...iconProps}>
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21a8 8 0 0 1 16 0" />
          </svg>
        }
      />
    </nav>
  );
}
