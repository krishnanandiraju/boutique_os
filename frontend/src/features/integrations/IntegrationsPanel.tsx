import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { ChannelConnection, IntegrationOutboxItem, IntegrationOutboxStatus } from '../../types'

const surfaceNames: Array<{ label: string; channel: string; role: string }> = [
  { label: 'BoutiqueOS Storefront', channel: 'BOUTIQUEOS', role: 'Owned storefront' },
  { label: 'Labha', channel: 'LABHA', role: 'Social commerce' },
  { label: 'Shopify', channel: 'SHOPIFY', role: 'Commerce channel' },
  { label: 'WhatsApp', channel: 'WHATSAPP', role: 'Customer messaging' },
  { label: 'Instagram', channel: 'INSTAGRAM', role: 'Discovery channel' },
  { label: 'Accounting', channel: 'MANUAL', role: 'Financial export seam' },
  { label: 'Payments', channel: 'MANUAL', role: 'Payment gateway seam' },
  { label: 'Logistics', channel: 'MANUAL', role: 'Shipment seam' },
]

function statusFromChannel(connection: ChannelConnection | undefined): ChannelConnection['status'] {
  return connection?.status || 'NOT_CONFIGURED'
}

function eventLabel(eventType: string): { title: string; explanation: string } {
  if (eventType === 'order.created') {
    return { title: 'Order ready for downstream processing', explanation: 'The order is committed in BoutiqueOS and can now trigger workflow, accounting, messaging or fulfillment.' }
  }
  if (eventType === 'inventory.changed') {
    return { title: 'Inventory availability changed', explanation: 'Physical inventory truth changed and connected selling surfaces can safely receive the new availability.' }
  }
  if (eventType.includes('payment')) {
    return { title: 'Payment activity', explanation: 'A financial integration event is waiting for, or has completed, downstream processing.' }
  }
  if (eventType.includes('shipment')) {
    return { title: 'Shipment activity', explanation: 'A logistics integration event is moving between BoutiqueOS and a shipping provider.' }
  }
  return { title: eventType.replaceAll('.', ' · '), explanation: 'Durable integration event recorded after the BoutiqueOS business transaction.' }
}

function prettyStatus(status: string): string {
  return status.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function IntegrationsPanel() {
  const [channels, setChannels] = useState<ChannelConnection[]>([])
  const [outbox, setOutbox] = useState<IntegrationOutboxItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    void (async () => {
      try {
        const [channelsRes, outboxRes] = await Promise.all([api.integrationChannels(), api.integrationOutbox()])
        if (!active) return
        setChannels(channelsRes)
        setOutbox(outboxRes)
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load integrations')
      } finally {
        if (active) setLoading(false)
      }
    })()

    return () => {
      active = false
    }
  }, [])

  async function refresh() {
    setError('')
    try {
      const [channelsRes, outboxRes] = await Promise.all([api.integrationChannels(), api.integrationOutbox()])
      setChannels(channelsRes)
      setOutbox(outboxRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh integrations')
    }
  }

  async function retryEvent(event: IntegrationOutboxItem) {
    setError('')
    try {
      const updated = await api.retryIntegrationOutboxItem(event.id)
      setOutbox((prev) => prev.map((row) => (row.id === updated.id ? updated : row)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry event')
    }
  }

  const pending = outbox.filter((event) => event.status === 'PENDING').length
  const failed = outbox.filter((event) => event.status === 'FAILED').length
  const processed = outbox.filter((event) => event.status === 'PROCESSED').length
  const channelLookup = new Map(channels.map((channel) => [channel.channel_type, channel]))

  return (
    <section className="integrations-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Integration control plane</p>
          <h3>Connections & durable activity</h3>
          <p className="state">BoutiqueOS commits business truth first. The outbox guarantees delivery hand-off; long-running orchestration belongs to the workflow engine.</p>
        </div>
        <button type="button" onClick={() => void refresh()}>Refresh</button>
      </div>

      {loading && <p className="state">Loading integrations...</p>}
      {error && <p className="error">{error}</p>}

      <div className="cards integrations-cards">
        <article className="card"><p>Pending hand-offs</p><h3>{pending}</h3><small>Safely recorded, awaiting processing</small></article>
        <article className="card"><p>Processed</p><h3>{processed}</h3><small>Delivered or handled successfully</small></article>
        <article className="card"><p>Need attention</p><h3>{failed}</h3><small>Retryable without changing core truth</small></article>
      </div>

      <div className="integration-boundary-strip">
        <div><strong>1 · Commit truth</strong><span>Order + inventory changes</span></div>
        <b>→</b>
        <div><strong>2 · Record event</strong><span>Transactional outbox</span></div>
        <b>→</b>
        <div><strong>3 · Orchestrate</strong><span>Workflow engine / adapters</span></div>
      </div>

      <div className="table-wrap">
        <table>
          <thead><tr><th>Surface</th><th>Purpose</th><th>Status</th></tr></thead>
          <tbody>
            {surfaceNames.map((surface, index) => {
              const connection = channelLookup.get(surface.channel as ChannelConnection['channel_type'])
              const status = statusFromChannel(connection)
              return (
                <tr key={`${surface.channel}-${index}`}>
                  <td><strong>{surface.label}</strong></td>
                  <td>{surface.role}</td>
                  <td><span className={`badge ${status.toLowerCase().replace('_', '-')}`}>{prettyStatus(status)}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="integration-activity">
        <div className="section-head"><div><h4>Business activity</h4><p className="state">Human-readable view of durable integration events.</p></div></div>
        {outbox.length === 0 && <div className="integration-event empty">No integration events yet. Create an order to generate durable activity.</div>}
        {outbox.map((event) => {
          const presentation = eventLabel(event.event_type)
          return (
            <article className="integration-event" key={event.id}>
              <div className={`event-state ${event.status.toLowerCase()}`} aria-hidden="true" />
              <div className="event-copy">
                <div className="event-title-row"><strong>{presentation.title}</strong><span className={`badge ${event.status.toLowerCase()}`}>{prettyStatus(event.status)}</span></div>
                <p>{presentation.explanation}</p>
                <small>{event.aggregate_type} #{event.aggregate_id} · attempts {event.attempt_count}</small>
                {event.last_error && <small className="error">{event.last_error}</small>}
              </div>
              <div>
                {event.status === ('FAILED' as IntegrationOutboxStatus) && <button type="button" onClick={() => void retryEvent(event)}>Retry</button>}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
