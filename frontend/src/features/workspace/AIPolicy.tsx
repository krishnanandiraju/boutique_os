import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Checkbox, Group, MultiSelect, NumberInput, Paper, Select, Stack, Table, Text, Title } from '@mantine/core'

const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
type ServiceId = 'standard_preview' | 'premium_preview_1' | 'design_studio_1'
type TenantPolicy = {
  enabled: boolean
  monthly_request_limit_per_customer: number
  allowed_segments: string[]
  enabled_services: ServiceId[]
  monthly_spending_limit_credits: number | null
}
type TenantService = {
  id: ServiceId
  name: string
  description: string
  enabled: boolean
  credits_per_success: number
  spending_limit_credits: number | null
}
type TenantResponse = {
  policy: TenantPolicy
  credit_balance: { available_credits: number; reserved_credits: number; spent_credits: number }
  services: TenantService[]
  usage_history: Array<{ created_at: string; entry_type: string; service_id: string | null; credits: number; note: string | null }>
}
type CustomerPolicy = { control: 'follow_segment_policy' | 'allow' | 'disable'; monthly_request_limit: number | null }

async function request(path: string, value?: unknown) {
  const response = await fetch(
    `${base}/api/ai-policy/${path}`,
    value === undefined ? undefined : { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) },
  )
  if (!response.ok) throw new Error('AI access settings are not connected. Ask your platform administrator to enable them.')
  return response.json()
}

export function AIPolicyAdmin() {
  const [policy, setPolicy] = useState<TenantPolicy | null>(null)
  const [services, setServices] = useState<TenantService[]>([])
  const [balance, setBalance] = useState<{ available_credits: number; reserved_credits: number; spent_credits: number } | null>(null)
  const [history, setHistory] = useState<TenantResponse['usage_history']>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  const serviceMap = useMemo(() => Object.fromEntries(services.map((service) => [service.id, service])), [services])

  async function load() {
    const data = (await request('tenant')) as TenantResponse
    setPolicy(data.policy)
    setServices(data.services)
    setBalance(data.credit_balance)
    setHistory(data.usage_history)
  }

  useEffect(() => {
    let active = true
    void request('tenant')
      .then((data) => {
        if (!active) return
        const payload = data as TenantResponse
        setPolicy(payload.policy)
        setServices(payload.services)
        setBalance(payload.credit_balance)
        setHistory(payload.usage_history)
      })
      .catch((error) => { if (active) setMessage((error as Error).message) })
    return () => { active = false }
  }, [])

  async function save() {
    if (!policy) return
    setBusy(true); setMessage('')
    try { await request('tenant', policy); await load(); setMessage('Tenant AI policy saved.') } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }

  async function saveService(service: TenantService) {
    setBusy(true); setMessage('')
    try {
      await request(`tenant/services/${service.id}`, {
        enabled: service.enabled,
        credits_per_success: service.credits_per_success,
        spending_limit_credits: service.spending_limit_credits,
      })
      await load()
      setMessage(`${service.name} configuration saved.`)
    } catch (error) {
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return <Paper withBorder p="lg"><Stack>
    <Title order={3}>AI services & customer eligibility</Title>
    <Text size="sm">Tenant credits are owned and funded at the business level. Customers never hold credit wallets.</Text>
    <Alert color="blue">Platform operations funds tenant credits. Tenant admins configure AI services, customer eligibility and anti-abuse request limits.</Alert>
    {message && <Text role="status">{message}</Text>}
    {policy && <>
      <Checkbox label="Enable AI previews for this tenant" checked={policy.enabled} onChange={(event) => setPolicy({ ...policy, enabled: event.currentTarget.checked })} />
      <MultiSelect label="Segment eligibility" data={['New', 'Repeat', 'VIP']} value={policy.allowed_segments} onChange={(allowed_segments) => setPolicy({ ...policy, allowed_segments })} />
      <NumberInput label="Monthly AI request limit per eligible customer" min={0} max={1000} value={policy.monthly_request_limit_per_customer} onChange={(value) => setPolicy({ ...policy, monthly_request_limit_per_customer: Number(value) || 0 })} />
      <NumberInput label="Tenant monthly AI spending cap (credits)" min={1} max={10000000} value={policy.monthly_spending_limit_credits ?? ''} onChange={(value) => setPolicy({ ...policy, monthly_spending_limit_credits: value === '' ? null : Number(value) || null })} />
      <MultiSelect label="Enabled AI services" data={[{ value: 'standard_preview', label: 'Standard Preview' }, { value: 'premium_preview_1', label: 'Premium Preview 1' }, { value: 'design_studio_1', label: 'Design Studio 1' }]} value={policy.enabled_services} onChange={(enabled_services) => setPolicy({ ...policy, enabled_services: enabled_services as ServiceId[] })} />

      {balance && <Group grow>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Available credits</Text><Text fw={800}>{balance.available_credits}</Text></Paper>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Reserved credits</Text><Text fw={800}>{balance.reserved_credits}</Text></Paper>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Spent credits</Text><Text fw={800}>{balance.spent_credits}</Text></Paper>
      </Group>}

      <Stack gap="xs">
        {policy.enabled_services.map((serviceId) => {
          const service = serviceMap[serviceId]
          if (!service) return null
          return <Paper withBorder p="sm" key={service.id}><Stack gap="xs">
            <Text fw={700}>{service.name}</Text>
            <Text size="sm" c="dimmed">{service.description}</Text>
            <Checkbox label="Service enabled" checked={service.enabled} onChange={(event) => setServices(services.map((current) => current.id === service.id ? { ...current, enabled: event.currentTarget.checked } : current))} />
            <NumberInput label="Credits per successful request" min={1} max={1000} value={service.credits_per_success} onChange={(value) => setServices(services.map((current) => current.id === service.id ? { ...current, credits_per_success: Number(value) || 1 } : current))} />
            <NumberInput label="Service spending cap (credits)" min={1} max={10000000} value={service.spending_limit_credits ?? ''} onChange={(value) => setServices(services.map((current) => current.id === service.id ? { ...current, spending_limit_credits: value === '' ? null : Number(value) || null } : current))} />
            <Button variant="light" loading={busy} onClick={() => void saveService(service)}>Save {service.name}</Button>
          </Stack></Paper>
        })}
      </Stack>

      <Button loading={busy} onClick={() => void save()}>Save tenant AI policy</Button>
      {!!history.length && <Table withTableBorder withColumnBorders><Table.Thead><Table.Tr><Table.Th>Time</Table.Th><Table.Th>Entry</Table.Th><Table.Th>Service</Table.Th><Table.Th>Credits</Table.Th><Table.Th>Note</Table.Th></Table.Tr></Table.Thead><Table.Tbody>
        {history.map((entry, index) => <Table.Tr key={`${entry.created_at}-${index}`}><Table.Td>{new Date(entry.created_at).toLocaleString('en-IN')}</Table.Td><Table.Td>{entry.entry_type}</Table.Td><Table.Td>{entry.service_id ?? '-'}</Table.Td><Table.Td>{entry.credits}</Table.Td><Table.Td>{entry.note ?? '-'}</Table.Td></Table.Tr>)}
      </Table.Tbody></Table>}
    </>}
  </Stack></Paper>
}

export function CustomerAIAccess({ customerId }: { customerId: number }) {
  const [policy, setPolicy] = useState<CustomerPolicy | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    void request(`customers/${customerId}`).then((data) => { if (active) setPolicy(data.policy) }).catch((error) => { if (active) setMessage(error.message) })
    return () => { active = false }
  }, [customerId])

  async function save() {
    if (!policy) return
    setBusy(true); setMessage('')
    try { await request(`customers/${customerId}`, policy); setMessage('Customer AI access saved.') } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }

  return <Paper withBorder p="md"><Stack>
    <Title order={4}>AI eligibility</Title>
    <Text size="sm">Control if this customer can request AI previews. This never creates a customer credit wallet.</Text>
    {message && <Text role="status">{message}</Text>}
    {policy && <>
      <Select label="Allow AI previews" value={policy.control} data={[{ value: 'follow_segment_policy', label: 'Follow segment policy' }, { value: 'allow', label: 'Allow' }, { value: 'disable', label: 'Disable' }]} onChange={(value) => setPolicy({ ...policy, control: (value || 'follow_segment_policy') as CustomerPolicy['control'] })} />
      <NumberInput label="Optional anti-abuse request limit (monthly)" description="Leave blank to use tenant-level limit." min={1} max={1000} value={policy.monthly_request_limit ?? ''} onChange={(value) => setPolicy({ ...policy, monthly_request_limit: value === '' ? null : Number(value) || null })} />
      <Button loading={busy} onClick={() => void save()}>Save AI eligibility</Button>
    </>}
  </Stack></Paper>
}
