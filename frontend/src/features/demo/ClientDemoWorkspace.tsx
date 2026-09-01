import { useEffect, useMemo, useState } from 'react'
import App from '../../App'
import { api } from '../../api'
import { IntegrationsPanel } from '../integrations/IntegrationsPanel'
import { StitchingPanel } from '../stitching'
import { DemoJourney } from './DemoJourney'
import type { AppNavKey } from '../../layout/AppShell'
import type { Customer, DashboardData } from '../../types'
import './client-demo.css'

type WorkspaceView = 'Overview' | 'Fit Memory' | 'Connections' | 'Operations'

const workspaceViews: Array<{ key: WorkspaceView; label: string; eyebrow: string }> = [
  { key: 'Overview', label: 'Overview', eyebrow: 'Story' },
  { key: 'Operations', label: 'Operations', eyebrow: 'Run' },
  { key: 'Fit Memory', label: 'Fit Memory', eyebrow: 'Learn' },
  { key: 'Connections', label: 'Connections', eyebrow: 'Extend' },
]

function money(value: string | number): string {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

export default function ClientDemoWorkspace() {
  const [view, setView] = useState<WorkspaceView>('Overview')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void Promise.all([api.dashboard(), api.customers()])
      .then(([dashboardResult, customerResult]) => {
        if (!active) return
        setDashboard(dashboardResult)
        setCustomers(customerResult)
        setSelectedCustomerId((current) => current ?? customerResult[0]?.id ?? null)
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : 'Unable to load demo workspace'))
      .finally(() => active && setLoading(false))

    return () => {
      active = false
    }
  }, [])

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.id === selectedCustomerId) || null,
    [customers, selectedCustomerId],
  )

  function handleJourneyNavigation(target: AppNavKey) {
    if (target === 'Fit Memory' || target === 'Customers') {
      setView('Fit Memory')
      return
    }
    if (target === 'Integrations') {
      setView('Connections')
      return
    }
    setView('Operations')
  }

  return (
    <div className="client-workspace">
      <aside className="client-sidebar">
        <div className="client-brand">
          <span className="client-brand-mark">B</span>
          <div>
            <strong>BoutiqueOS</strong>
            <small>Retail · Tailoring · Fit intelligence</small>
          </div>
        </div>

        <div className="workspace-label">Workspace</div>
        <div className="client-nav" role="navigation" aria-label="Demo workspace">
          {workspaceViews.map((item) => (
            <button
              key={item.key}
              type="button"
              className={view === item.key ? 'client-nav-item active' : 'client-nav-item'}
              onClick={() => setView(item.key)}
            >
              <span>{item.eyebrow}</span>
              <strong>{item.label}</strong>
            </button>
          ))}
        </div>

        <div className="client-sidebar-card">
          <span className="live-dot" />
          <div>
            <small>Demo merchant</small>
            <strong>Meera Boutique</strong>
          </div>
        </div>
        <p className="client-sidebar-note">BoutiqueOS is the operational source of truth. Selling channels and downstream systems remain replaceable.</p>
      </aside>

      <main className="client-main">
        <header className="client-topbar">
          <div>
            <p className="client-kicker">Client demonstration workspace</p>
            <h1>{view}</h1>
          </div>
          <div className="client-topbar-actions">
            <span className="demo-pill">DEMO MODE</span>
            <button type="button" className="secondary-action" onClick={() => setView('Operations')}>Open operations</button>
          </div>
        </header>

        {error && <div className="client-alert error">{error}</div>}
        {loading && <div className="client-alert">Loading boutique workspace…</div>}

        {view === 'Overview' && (
          <div className="client-page-stack">
            <section className="client-hero-panel">
              <div>
                <p className="client-kicker">One boutique operating system</p>
                <h2>Sell the exact piece. Stitch it right. Remember what the customer actually liked.</h2>
                <p className="hero-copy">From one-off garments and fabric rolls to measurement history, tailoring work and external commerce channels, BoutiqueOS keeps the operational truth in one place.</p>
                <div className="hero-actions">
                  <button type="button" onClick={() => setView('Operations')}>Run boutique operations</button>
                  <button type="button" className="secondary-action" onClick={() => setView('Fit Memory')}>Show Fit Memory</button>
                </div>
              </div>
              <div className="hero-proof-stack">
                <div><span>01</span><strong>Unique inventory protected</strong><small>Hold and sell without double-selling</small></div>
                <div><span>02</span><strong>Measurements stay historical</strong><small>Every version remains traceable to the stitch</small></div>
                <div><span>03</span><strong>Fit feedback becomes memory</strong><small>Sleeve too long. Neckline too deep. Remember it.</small></div>
              </div>
            </section>

            {dashboard && (
              <section className="executive-grid" aria-label="Boutique overview metrics">
                <article className="executive-card primary"><span>Sales today</span><strong>{money(dashboard.sales_today)}</strong><small>Live operating snapshot</small></article>
                <article className="executive-card"><span>Available pieces</span><strong>{dashboard.available_items}</strong><small>Ready to sell</small></article>
                <article className="executive-card"><span>Held pieces</span><strong>{dashboard.held_items}</strong><small>Protected from double-sell</small></article>
                <article className="executive-card"><span>Pending orders</span><strong>{dashboard.orders_pending}</strong><small>Need action</small></article>
                <article className="executive-card"><span>Tailoring jobs</span><strong>{dashboard.tailoring_pending}</strong><small>In the work queue</small></article>
                <article className="executive-card"><span>Fabric remnants</span><strong>{dashboard.remnant_rolls}</strong><small>Visible rather than forgotten</small></article>
              </section>
            )}

            <DemoJourney onNavigate={handleJourneyNavigation} />

            <section className="architecture-story">
              <div>
                <p className="client-kicker">The boundary that matters</p>
                <h2>BoutiqueOS owns truth. Workflow and channels orchestrate around it.</h2>
              </div>
              <div className="architecture-flow">
                <div><strong>BoutiqueOS Core</strong><span>Inventory · Customer · Measurements · Orders · Stitch records</span></div>
                <b>→</b>
                <div><strong>Transactional Outbox</strong><span>Durable events · retry metadata · idempotency</span></div>
                <b>→</b>
                <div><strong>Workflow / Integrations</strong><span>Temporal later · Labha · Shopify · WhatsApp · ERP</span></div>
              </div>
            </section>
          </div>
        )}

        {view === 'Operations' && (
          <section className="embedded-operations">
            <div className="embedded-context">
              <div>
                <p className="client-kicker">Operational workspace</p>
                <h2>Catalog, customers, orders, lots and tailoring</h2>
              </div>
              <span className="context-chip">Existing workflows preserved</span>
            </div>
            <App />
          </section>
        )}

        {view === 'Fit Memory' && (
          <section className="client-page-stack">
            <div className="fit-memory-header">
              <div>
                <p className="client-kicker">Customer intelligence that belongs to the boutique</p>
                <h2>Measurement Book + Stitch Feedback = Fit Memory</h2>
                <p>Measurements capture the body. Stitch records capture what was made. Trial feedback captures how it felt. We keep those facts separate so history stays trustworthy.</p>
              </div>
              <label className="customer-picker">
                <span>Customer</span>
                <select value={selectedCustomerId ?? ''} onChange={(event) => setSelectedCustomerId(Number(event.target.value))}>
                  {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} · {customer.phone}</option>)}
                </select>
              </label>
            </div>

            <div className="fit-principles">
              <article><span>Body fact</span><strong>Measurement version</strong><p>Immutable historical dimensions used for an order.</p></article>
              <article><span>Stitch fact</span><strong>Stitch record</strong><p>Garment type, tailor, stage and the exact measurement version used.</p></article>
              <article><span>Learned signal</span><strong>Trial feedback</strong><p>Structured fit observations such as sleeve too long or neck too deep.</p></article>
            </div>

            {selectedCustomer ? (
              <StitchingPanel customerId={selectedCustomer.id} customerName={selectedCustomer.name} />
            ) : (
              <div className="client-empty">Create a customer in Operations to start building Fit Memory.</div>
            )}
          </section>
        )}

        {view === 'Connections' && (
          <section className="client-page-stack">
            <div className="connections-hero">
              <div>
                <p className="client-kicker">Composable commerce</p>
                <h2>Connect selling, money, logistics and messaging without surrendering boutique truth.</h2>
                <p>Integration events are durable. Long-running business workflows belong behind a workflow port rather than inside a hand-built queue.</p>
              </div>
              <div className="connection-legend">
                <span><i className="legend-core" /> Core truth</span>
                <span><i className="legend-event" /> Durable event</span>
                <span><i className="legend-edge" /> External system</span>
              </div>
            </div>
            <IntegrationsPanel />
          </section>
        )}
      </main>
    </div>
  )
}
