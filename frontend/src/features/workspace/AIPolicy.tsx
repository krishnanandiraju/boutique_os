import { useEffect, useState } from 'react'
import { Alert, Button, Checkbox, MultiSelect, NumberInput, Paper, Select, Stack, Text, Title } from '@mantine/core'

const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
type TenantPolicy = { enabled: boolean; monthly_customer_limit: number; allowed_segments: string[]; enabled_services: string[] }
type CustomerPolicy = { access: 'off' | 'inherit' | 'allow'; monthly_limit: number }
async function request(path: string, value?: unknown) {
  const response = await fetch(`${base}/api/ai-policy/${path}`, value === undefined ? undefined : { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) })
  if (!response.ok) throw new Error('AI access settings are not connected. Ask your platform administrator to enable them.')
  return response.json()
}

export function AIPolicyAdmin() {
  const [policy, setPolicy] = useState<TenantPolicy | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { let active = true; request('tenant').then(data => { if (active) setPolicy(data.policy) }).catch(error => { if (active) setMessage(error.message) }); return () => { active = false } }, [])
  async function save() {
    setBusy(true); setMessage('')
    try { await request('tenant', policy); setMessage('AI access policy saved.') } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }
  return <Paper withBorder p="lg"><Stack><Title order={3}>AI services & customer access</Title>
    <Text size="sm">Choose which customers receive AI previews and set their monthly allowance.</Text>
    <Alert color="yellow">Policy configuration foundation. Credit accounting and request enforcement must be connected before these limits control previews. Credit balance is not connected.</Alert>
    {message && <Text role="status">{message}</Text>}
    {policy && <>
      <Checkbox label="Enable AI benefits for this boutique" checked={policy.enabled} onChange={event => setPolicy({ ...policy, enabled: event.currentTarget.checked })} />
      <MultiSelect label="Eligible customer segments" data={['New', 'Repeat', 'VIP']} value={policy.allowed_segments} onChange={allowed_segments => setPolicy({ ...policy, allowed_segments })} />
      <NumberInput label="Monthly AI credit allowance per eligible customer" min={0} max={1000} value={policy.monthly_customer_limit} onChange={value => setPolicy({ ...policy, monthly_customer_limit: Number(value) || 0 })} />
      <MultiSelect label="Enabled AI services" data={[{ value: 'standard_preview', label: 'Standard Preview — supported finished garments' }, { value: 'premium_preview_1', label: 'Premium Preview 1 — additional preview options' }, { value: 'design_studio_1', label: 'Design Studio 1 — fabric to garment concept' }]} value={policy.enabled_services} onChange={enabled_services => setPolicy({ ...policy, enabled_services })} />
      <Text size="sm">Standard Preview: provisional 1 credit per successful request. Premium and design pricing await platform configuration. Enabling a service does not connect it.</Text>
      <Button loading={busy} onClick={() => void save()}>Save AI access policy</Button>
    </>}
  </Stack></Paper>
}

export function CustomerAIAccess({ customerId }: { customerId: number }) {
  const [policy, setPolicy] = useState<CustomerPolicy | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { let active = true; request(`customers/${customerId}`).then(data => { if (active) setPolicy(data.policy) }).catch(error => { if (active) setMessage(error.message) }); return () => { active = false } }, [customerId])
  async function save() {
    setBusy(true); setMessage('')
    try { await request(`customers/${customerId}`, policy); setMessage('Customer AI access saved.') } catch (error) { setMessage((error as Error).message) } finally { setBusy(false) }
  }
  return <Paper withBorder p="md"><Stack><Title order={4}>AI benefits</Title>
    <Text size="sm">Customer segment describes the relationship. AI access controls the benefit separately.</Text>
    {message && <Text role="status">{message}</Text>}
    {policy && <>
      <Select label="AI access" value={policy.access} data={[{ value: 'off', label: 'Off' }, { value: 'inherit', label: 'Follow boutique policy' }, { value: 'allow', label: 'Individual allowance' }]} onChange={value => setPolicy({ ...policy, access: (value || 'inherit') as CustomerPolicy['access'] })} />
      {policy.access === 'allow' && <NumberInput label="Monthly AI credit allowance" min={0} max={1000} value={policy.monthly_limit} onChange={value => setPolicy({ ...policy, monthly_limit: Number(value) || 0 })} />}
      <Button loading={busy} onClick={() => void save()}>Save AI benefits</Button>
    </>}
  </Stack></Paper>
}
