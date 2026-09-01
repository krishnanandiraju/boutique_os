import type { AppNavKey } from '../../layout/AppShell'

const steps: Array<{ nav: AppNavKey; number: string; title: string; copy: string; proof: string }> = [
  { nav: 'Catalog', number: '01', title: 'Capture the garment', copy: 'Create the product once, attach media, and make it the canonical boutique catalog record.', proof: 'Unique piece · stocked SKU · fabric roll' },
  { nav: 'Customers', number: '02', title: 'Remember the customer', copy: 'Keep versioned body measurements and purchase history tied to the customer.', proof: 'Measurement Book' },
  { nav: 'Orders', number: '03', title: 'Sell without double-selling', copy: 'Create one mixed order while BoutiqueOS allocates the exact physical lots and rolls.', proof: 'Atomic allocation' },
  { nav: 'Tailoring', number: '04', title: 'Move into tailoring', copy: 'Turn tailored lines into visible work with stages, due dates, assignments, and trial handling.', proof: 'Operational workflow' },
  { nav: 'Fit Memory', number: '05', title: 'Learn from the stitch', copy: 'Record feedback such as sleeve too long or neckline too deep without overwriting historical measurements.', proof: 'Fit Memory' },
  { nav: 'Integrations', number: '06', title: 'Project outward', copy: 'Publish or synchronize through commerce, accounting, payment, logistics, and messaging adapters.', proof: 'Labha · Shopify · WhatsApp · ERP' },
]

export function DemoJourney({ onNavigate }: { onNavigate: (key: AppNavKey) => void }) {
  return (
    <section className="demo-journey">
      <header className="demo-hero">
        <div>
          <p className="eyebrow">Boutique operating system</p>
          <h1>From garment photo to a better-fitting repeat customer.</h1>
          <p>BoutiqueOS keeps the physical merchandise, customer fit memory, order, and tailoring truth together while external channels remain replaceable integrations.</p>
        </div>
        <div className="demo-hero-proof">
          <strong>One operational truth</strong>
          <span>Sell anywhere. Stitch with memory.</span>
        </div>
      </header>

      <div className="journey-grid">
        {steps.map((step) => (
          <button type="button" key={step.number} className="journey-card" onClick={() => onNavigate(step.nav)}>
            <span className="journey-number">{step.number}</span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
              <small>{step.proof}</small>
            </div>
            <span aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </section>
  )
}
