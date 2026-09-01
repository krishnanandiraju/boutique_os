import type { ReactNode } from 'react'

export type AppNavKey = 'Dashboard' | 'Catalog' | 'Customers' | 'Orders' | 'Tailoring' | 'Fit Memory' | 'Integrations'

const navItems: AppNavKey[] = ['Dashboard', 'Catalog', 'Customers', 'Orders', 'Tailoring', 'Fit Memory', 'Integrations']

export function AppShell({
  active,
  onNavigate,
  children,
}: {
  active: AppNavKey
  onNavigate: (key: AppNavKey) => void
  children: ReactNode
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">B</span>
          <div><strong>BoutiqueOS</strong><small>Operate · Fit · Sell</small></div>
        </div>
        <nav aria-label="Primary navigation">
          {navItems.map((item) => (
            <button
              key={item}
              type="button"
              className={active === item ? 'active' : ''}
              aria-current={active === item ? 'page' : undefined}
              onClick={() => onNavigate(item)}
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <small>Demo workspace</small>
          <strong>Meera Boutique</strong>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  )
}
