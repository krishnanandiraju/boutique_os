import { useEffect, useState } from 'react'
import { Alert, Badge, Button, Checkbox, Divider, Group, NumberInput, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { Plus, Save } from 'lucide-react'
import { domainV2Api, type DiscountRule, type MerchantPolicy, type Supplier } from '../../domainV2Api'

const stageOptions = [
  { value: 'MEASUREMENT_PENDING', label: 'Measurement pending' },
  { value: 'CUTTING', label: 'Cutting started' },
  { value: 'STITCHING', label: 'Stitching started' },
  { value: 'QC', label: 'Quality check' },
]

export function OperatingPolicyPanel() {
  const [policy, setPolicy] = useState<MerchantPolicy | null>(null)
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [rules, setRules] = useState<DiscountRule[]>([])
  const [supplierName, setSupplierName] = useState('')
  const [discountName, setDiscountName] = useState('')
  const [discountValue, setDiscountValue] = useState<number | string>(10)
  const [discountKind, setDiscountKind] = useState<'PERCENTAGE' | 'FLAT'>('PERCENTAGE')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function refresh() {
    void Promise.all([domainV2Api.merchantPolicy(), domainV2Api.suppliers(), domainV2Api.discountRules()])
      .then(([p, s, r]) => { setPolicy(p); setSuppliers(s); setRules(r) })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load operating policy.'))
  }
  useEffect(refresh, [])

  async function savePolicy() {
    if (!policy) return
    setSaving(true); setError(''); setMessage('')
    try {
      const saved = await domainV2Api.saveMerchantPolicy({
        measurement_edit_mode: policy.measurement_edit_mode,
        measurement_grace_hours: policy.measurement_grace_hours,
        measurement_lock_stage: policy.measurement_lock_stage,
        post_lock_requires_approval: policy.post_lock_requires_approval,
        dashboard_config: policy.dashboard_config,
      })
      setPolicy(saved); setMessage('Operating policy saved.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save operating policy.') } finally { setSaving(false) }
  }

  async function addSupplier() {
    if (!supplierName.trim()) return
    setError('')
    try { await domainV2Api.createSupplier({ name: supplierName.trim() }); setSupplierName(''); refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to add supplier.') }
  }

  async function addDiscountRule() {
    if (!discountName.trim() || !discountValue) return
    setError('')
    try {
      await domainV2Api.createDiscountRule({ name: discountName.trim(), kind: discountKind, scope: 'ORDER', value: String(discountValue), requires_reason: true, stackable: false })
      setDiscountName(''); setDiscountValue(10); refresh()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to add discount rule.') }
  }

  return <Stack gap="lg">
    {error && <Alert color="red">{error}</Alert>}{message && <Alert color="teal">{message}</Alert>}
    <Paper withBorder p="lg">
      <Stack gap="md">
        <div><Title order={3}>Measurement change policy</Title><Text size="sm" c="dimmed">Body measurements stay versioned. This policy controls when a merchant allows corrections once tailoring starts.</Text></div>
        {policy && <>
          <SimpleGrid cols={{ base: 1, md: 3 }}>
            <Select label="Edit policy" value={policy.measurement_edit_mode} data={[{ value: 'UNTIL_STAGE', label: 'Editable until a stage' }, { value: 'TIME_WINDOW', label: 'Editable within a time window' }, { value: 'STAGE_AND_TIME', label: 'Stage and time window' }, { value: 'APPROVAL_AFTER_STAGE', label: 'Approval after stage' }]} onChange={(value) => value && setPolicy({ ...policy, measurement_edit_mode: value as MerchantPolicy['measurement_edit_mode'] })} />
            <Select label="Lock stage" value={policy.measurement_lock_stage} data={stageOptions} onChange={(value) => value && setPolicy({ ...policy, measurement_lock_stage: value })} />
            <NumberInput label="Grace period (hours)" min={0} max={720} allowDecimal={false} value={policy.measurement_grace_hours ?? ''} onChange={(value) => setPolicy({ ...policy, measurement_grace_hours: value === '' ? null : Number(value) })} />
          </SimpleGrid>
          <Checkbox label="After lock, require approval instead of silently changing measurements" checked={policy.post_lock_requires_approval} onChange={(event) => setPolicy({ ...policy, post_lock_requires_approval: event.currentTarget.checked })} />
          <Group justify="flex-end"><Button color="grape" leftSection={<Save size={16} />} loading={saving} onClick={() => void savePolicy()}>Save policy</Button></Group>
        </>}
      </Stack>
    </Paper>

    <SimpleGrid cols={{ base: 1, lg: 2 }}>
      <Paper withBorder p="lg"><Stack gap="md"><div><Title order={3}>Suppliers</Title><Text size="sm" c="dimmed">Supplier records are part of BoutiqueOS; purchasing workflows can build on them later.</Text></div><Group align="flex-end"><TextInput label="Supplier name" placeholder="e.g. Sri Lakshmi Silks" value={supplierName} onChange={(event) => setSupplierName(event.currentTarget.value)} style={{ flex: 1 }} /><Button color="grape" leftSection={<Plus size={16} />} onClick={() => void addSupplier()}>Add</Button></Group><Divider />{suppliers.length === 0 ? <Text size="sm" c="dimmed">No suppliers yet.</Text> : <Stack gap="xs">{suppliers.map((supplier) => <Group key={supplier.id} justify="space-between"><Text fw={700}>{supplier.name}</Text><Badge variant="light" color="teal">Active</Badge></Group>)}</Stack>}</Stack></Paper>

      <Paper withBorder p="lg"><Stack gap="md"><div><Title order={3}>Discount policy</Title><Text size="sm" c="dimmed">Rules are explicit and auditable. Manual, promotional and role-limited discounting can share the same engine.</Text></div><TextInput label="Rule name" placeholder="e.g. Sales discretionary" value={discountName} onChange={(event) => setDiscountName(event.currentTarget.value)} /><SimpleGrid cols={2}><Select label="Type" value={discountKind} data={[{ value: 'PERCENTAGE', label: 'Percentage' }, { value: 'FLAT', label: 'Flat amount' }]} onChange={(value) => value && setDiscountKind(value as 'PERCENTAGE' | 'FLAT')} /><NumberInput label={discountKind === 'PERCENTAGE' ? 'Percent' : 'Amount'} min={0} value={discountValue} onChange={setDiscountValue} /></SimpleGrid><Button variant="light" color="grape" leftSection={<Plus size={16} />} onClick={() => void addDiscountRule()}>Add rule</Button><Divider />{rules.length === 0 ? <Text size="sm" c="dimmed">No discount rules yet.</Text> : <Stack gap="xs">{rules.map((rule) => <Group key={rule.id} justify="space-between"><div><Text fw={700}>{rule.name}</Text><Text size="xs" c="dimmed">{rule.scope.toLowerCase()} · reason required {rule.requires_reason ? 'yes' : 'no'}</Text></div><Badge variant="light" color="grape">{rule.kind === 'PERCENTAGE' ? `${Number(rule.value)}%` : `₹${Number(rule.value).toLocaleString('en-IN')}`}</Badge></Group>)}</Stack>}</Stack></Paper>
    </SimpleGrid>
  </Stack>
}
