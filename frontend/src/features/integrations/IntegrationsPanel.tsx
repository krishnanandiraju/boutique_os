import { useEffect, useState } from 'react'
import { api } from '../../api'
import type { ChannelConnection, IntegrationOutboxItem, IntegrationOutboxStatus } from '../../types'

const surfaceNames: Array<{ label: string; channel: string }> = [
  { label: 'BoutiqueOS Storefront', channel: 'BOUTIQUEOS' },
  { label: 'Labha', channel: 'LABHA' },
  { label: 'Shopify', channel: 'SHOPIFY' },
  { label: 'WhatsApp', channel: 'WHATSAPP' },
  { label: 'Instagram', channel: 'INSTAGRAM' },
  { label: 'Accounting', channel: 'MANUAL' },
  { label: 'Payments', channel: 'MANUAL' },
  { label: 'Logistics', channel: 'MANUAL' },
]

function statusFromChannel(connection: ChannelConnection | undefined): ChannelConnection['status'] {
  return connection?.status || 'NOT_CONFIGURED'
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
  const channelLookup = new Map(channels.map((channel) => [channel.channel_type, channel]))

  return (
    <section className="integrations-panel">
      <div className="section-head">
        <h3>Integrations</h3>
        <button type="button" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      {loading && <p className="state">Loading integrations...</p>}
      {error && <p className="error">{error}</p>}

      <div className="cards integrations-cards">
        <article className="card"><p>Pending Events</p><h3>{pending}</h3></article>
        <article className="card"><p>Failed Events</p><h3>{failed}</h3></article>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Surface</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {surfaceNames.map((surface) => {
              const connection = channelLookup.get(surface.channel as ChannelConnection['channel_type'])
              return (
                <tr key={surface.channel}>
                  <td>{surface.label}</td>
                  <td><span className={`badge ${statusFromChannel(connection).toLowerCase().replace('_', '-')}`}>{statusFromChannel(connection)}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Event</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Aggregate</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {outbox.map((event) => (
              <tr key={event.id}>
                <td>{event.event_type}</td>
                <td>{event.status}</td>
                <td>{event.attempt_count}</td>
                <td>{event.aggregate_type} #{event.aggregate_id}</td>
                <td>
                  {event.status === ('FAILED' as IntegrationOutboxStatus) ? (
                    <button type="button" onClick={() => void retryEvent(event)}>
                      Retry
                    </button>
                  ) : (
                    '-'
                  )}
                </td>
              </tr>
            ))}
            {outbox.length === 0 && (
              <tr>
                <td colSpan={5}>No integration events queued.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
