import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, Checkbox, Divider, Group, Modal, NumberInput, Paper, Select, SimpleGrid, Stack, Text, TextInput, Textarea, Title } from '@mantine/core'
import { CalendarHeart, Save, Sparkles } from 'lucide-react'
import type { Customer } from '../../types'
import { customerCrmApi, type CustomerOccasion, type CustomerProfile } from '../../customerCrmApi'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

type ProfileForm = Omit<CustomerProfile, 'id' | 'customer_id' | 'updated_at' | 'metrics'>

const emptyProfile: ProfileForm = {
  address_line1: null,
  address_line2: null,
  city: null,
  state: null,
  postal_code: null,
  country: 'India',
  date_of_birth: null,
  anniversary_date: null,
  preferred_language: null,
  acquisition_source: null,
  acquisition_detail: null,
  customer_segment: null,
  merchant_tags: [],
  preferences: {},
  marketing_consent: true,
}

export function CustomerCrmModal({ customer, opened, onClose, onSaved }: { customer: Customer | null; opened: boolean; onClose: () => void; onSaved: () => void }) {
  const [profile, setProfile] = useState<CustomerProfile | null>(null)
  const [form, setForm] = useState<ProfileForm>(emptyProfile)
  const [occasions, setOccasions] = useState<CustomerOccasion[]>([])
  const [tagsText, setTagsText] = useState('')
  const [styleNotes, setStyleNotes] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [eventForm, setEventForm] = useState({ occasion_type: 'WEDDING_ANNIVERSARY' as CustomerOccasion['occasion_type'], label: 'Wedding anniversary', event_date: '', recurring_annually: true, offer_kind: 'PERCENTAGE' as CustomerOccasion['offer_kind'], offer_value: '10', offer_code: '', lead_days: 14, notes: '' })

  function load(customerId: number) {
    setError(''); setNotice('')
    void Promise.all([customerCrmApi.profile(customerId), customerCrmApi.occasions(customerId)])
      .then(([nextProfile, nextOccasions]) => {
        setProfile(nextProfile)
        setForm({
          address_line1: nextProfile.address_line1,
          address_line2: nextProfile.address_line2,
          city: nextProfile.city,
          state: nextProfile.state,
          postal_code: nextProfile.postal_code,
          country: nextProfile.country,
          date_of_birth: nextProfile.date_of_birth,
          anniversary_date: nextProfile.anniversary_date,
          preferred_language: nextProfile.preferred_language,
          acquisition_source: nextProfile.acquisition_source,
          acquisition_detail: nextProfile.acquisition_detail,
          customer_segment: nextProfile.customer_segment,
          merchant_tags: nextProfile.merchant_tags,
          preferences: nextProfile.preferences,
          marketing_consent: nextProfile.marketing_consent,
        })
        setTagsText(nextProfile.merchant_tags.join(', '))
        setStyleNotes(String(nextProfile.preferences.style_notes ?? ''))
        setOccasions(nextOccasions)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load CRM profile.'))
  }

  useEffect(() => {
    if (opened && customer) load(customer.id)
  }, [opened, customer?.id])

  const nextOccasion = useMemo(() => occasions[0] ?? null, [occasions])

  async function save() {
    if (!customer) return
    setSaving(true); setError(''); setNotice('')
    try {
      const payload: ProfileForm = {
        ...form,
        merchant_tags: tagsText.split(',').map((value) => value.trim()).filter(Boolean),
        preferences: { ...form.preferences, style_notes: styleNotes },
      }
      const saved = await customerCrmApi.saveProfile(customer.id, payload)
      setProfile(saved)
      setForm(payload)
      setNotice('Customer profile saved.')
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save customer profile.') } finally { setSaving(false) }
  }

  async function addOccasion() {
    if (!customer || !eventForm.event_date || !eventForm.label) return
    setError(''); setNotice('')
    try {
      await customerCrmApi.addOccasion(customer.id, eventForm)
      setEventForm({ ...eventForm, label: 'Wedding anniversary', event_date: '', offer_code: '' })
      setNotice('Customer occasion added.')
      load(customer.id)
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to add occasion.') }
  }

  return <Modal opened={opened} onClose={onClose} title={customer ? `${customer.name} · CRM profile` : 'Customer profile'} size="xl" centered>
    <Stack gap="lg">
      {error && <Alert color="red">{error}</Alert>}
      {notice && <Alert color="teal">{notice}</Alert>}
      {profile && <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Orders</Text><Text fw={800}>{profile.metrics.order_count}</Text></Paper>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Lifetime spend</Text><Text fw={800}>{money(profile.metrics.total_spend)}</Text></Paper>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Average order</Text><Text fw={800}>{money(profile.metrics.average_order_value)}</Text></Paper>
        <Paper withBorder p="sm"><Text size="xs" c="dimmed">Est. gross margin</Text><Text fw={800}>{money(profile.metrics.estimated_gross_margin)}</Text></Paper>
      </SimpleGrid>}

      {nextOccasion && <Paper withBorder p="md">
        <Group justify="space-between"><Group><CalendarHeart size={18} /><div><Text fw={800}>Next customer moment</Text><Text size="sm" c="dimmed">{nextOccasion.label} · {new Date(`${nextOccasion.next_occurrence}T00:00:00`).toLocaleDateString('en-IN')}</Text></div></Group>{nextOccasion.offer_kind !== 'NONE' && <Badge color="grape" variant="light">{nextOccasion.offer_kind === 'PERCENTAGE' ? `${Number(nextOccasion.offer_value)}% offer` : nextOccasion.offer_kind === 'FLAT' ? `${money(nextOccasion.offer_value ?? 0)} offer` : 'Gift offer'}</Badge>}</Group>
      </Paper>}

      <div><Title order={4}>Customer context</Title><Text size="sm" c="dimmed">Operational customer information BoutiqueOS needs for selling, service and personalization.</Text></div>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <TextInput label="Address line 1" value={form.address_line1 ?? ''} onChange={(e) => setForm({ ...form, address_line1: e.currentTarget.value || null })} />
        <TextInput label="Address line 2" value={form.address_line2 ?? ''} onChange={(e) => setForm({ ...form, address_line2: e.currentTarget.value || null })} />
        <TextInput label="City" value={form.city ?? ''} onChange={(e) => setForm({ ...form, city: e.currentTarget.value || null })} />
        <TextInput label="State" value={form.state ?? ''} onChange={(e) => setForm({ ...form, state: e.currentTarget.value || null })} />
        <TextInput label="PIN / postal code" value={form.postal_code ?? ''} onChange={(e) => setForm({ ...form, postal_code: e.currentTarget.value || null })} />
        <TextInput label="Preferred language" value={form.preferred_language ?? ''} onChange={(e) => setForm({ ...form, preferred_language: e.currentTarget.value || null })} />
        <TextInput label="Date of birth" type="date" value={form.date_of_birth ?? ''} onChange={(e) => setForm({ ...form, date_of_birth: e.currentTarget.value || null })} />
        <TextInput label="Anniversary date" type="date" value={form.anniversary_date ?? ''} onChange={(e) => setForm({ ...form, anniversary_date: e.currentTarget.value || null })} />
        <Select label="Acquisition source" clearable searchable data={['Walk-in', 'Instagram', 'WhatsApp', 'Referral', 'Exhibition', 'Website', 'Marketplace', 'Other']} value={form.acquisition_source} onChange={(value) => setForm({ ...form, acquisition_source: value })} />
        <TextInput label="Acquisition detail" placeholder="Referral name, campaign, exhibition..." value={form.acquisition_detail ?? ''} onChange={(e) => setForm({ ...form, acquisition_detail: e.currentTarget.value || null })} />
        <TextInput label="Customer segment" placeholder="VIP, Bridal, Regular..." value={form.customer_segment ?? ''} onChange={(e) => setForm({ ...form, customer_segment: e.currentTarget.value || null })} />
        <TextInput label="Merchant tags" description="Comma separated; searchable customer memory." placeholder="VIP, bridal, prefers pastels" value={tagsText} onChange={(e) => setTagsText(e.currentTarget.value)} />
      </SimpleGrid>
      <Textarea label="Style / service preferences" placeholder="Preferred fits, colours, fabrics, service notes..." minRows={3} value={styleNotes} onChange={(e) => setStyleNotes(e.currentTarget.value)} />
      <Checkbox label="Marketing consent" checked={form.marketing_consent} onChange={(e) => setForm({ ...form, marketing_consent: e.currentTarget.checked })} />
      <Group justify="flex-end"><Button color="grape" leftSection={<Save size={16} />} loading={saving} onClick={() => void save()}>Save CRM profile</Button></Group>

      <Divider />
      <div><Group gap="xs"><Sparkles size={18} /><Title order={4}>Customer occasions & offers</Title></Group><Text size="sm" c="dimmed">Birthdays, anniversaries and boutique-defined moments can carry a suggested offer without hard-coding campaign logic.</Text></div>
      <Stack gap="xs">{occasions.map((occasion) => <Paper key={occasion.id} withBorder p="sm"><Group justify="space-between" align="flex-start"><div><Text fw={800}>{occasion.label}</Text><Text size="sm" c="dimmed">Next: {new Date(`${occasion.next_occurrence}T00:00:00`).toLocaleDateString('en-IN')}{occasion.anniversary_number ? ` · ${occasion.anniversary_number}${occasion.anniversary_number === 1 ? 'st' : occasion.anniversary_number === 2 ? 'nd' : occasion.anniversary_number === 3 ? 'rd' : 'th'} anniversary` : ''}</Text></div><Group gap="xs">{occasion.offer_kind !== 'NONE' && <Badge color="grape" variant="light">{occasion.offer_kind}{occasion.offer_value ? ` ${occasion.offer_value}` : ''}</Badge>}{occasion.offer_code && <Badge variant="outline">{occasion.offer_code}</Badge>}</Group></Group></Paper>)}</Stack>
      <Paper withBorder p="md"><Stack>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select label="Occasion type" data={[{value:'BIRTHDAY',label:'Birthday'},{value:'WEDDING_ANNIVERSARY',label:'Wedding anniversary'},{value:'FIRST_PURCHASE_ANNIVERSARY',label:'First-purchase anniversary'},{value:'CUSTOM',label:'Custom event'}]} value={eventForm.occasion_type} onChange={(value) => value && setEventForm({ ...eventForm, occasion_type: value as CustomerOccasion['occasion_type'] })} />
          <TextInput label="Label" value={eventForm.label} onChange={(e) => setEventForm({ ...eventForm, label: e.currentTarget.value })} />
          <TextInput label="Original event date" type="date" value={eventForm.event_date} onChange={(e) => setEventForm({ ...eventForm, event_date: e.currentTarget.value })} />
          <Select label="Suggested offer" data={[{value:'PERCENTAGE',label:'Percentage discount'},{value:'FLAT',label:'Flat discount'},{value:'GIFT',label:'Gift / benefit'},{value:'NONE',label:'No offer'}]} value={eventForm.offer_kind} onChange={(value) => value && setEventForm({ ...eventForm, offer_kind: value as CustomerOccasion['offer_kind'] })} />
          {['PERCENTAGE', 'FLAT'].includes(eventForm.offer_kind) && <TextInput label={eventForm.offer_kind === 'PERCENTAGE' ? 'Discount %' : 'Discount amount'} type="number" value={eventForm.offer_value} onChange={(e) => setEventForm({ ...eventForm, offer_value: e.currentTarget.value })} />}
          <TextInput label="Offer code" placeholder="ANNIV10" value={eventForm.offer_code} onChange={(e) => setEventForm({ ...eventForm, offer_code: e.currentTarget.value })} />
          <NumberInput label="Remind before (days)" min={0} max={365} value={eventForm.lead_days} onChange={(value) => setEventForm({ ...eventForm, lead_days: Number(value) || 0 })} />
          <Checkbox mt="xl" label="Repeat every year" checked={eventForm.recurring_annually} onChange={(e) => setEventForm({ ...eventForm, recurring_annually: e.currentTarget.checked })} />
        </SimpleGrid>
        <Textarea label="Occasion notes" value={eventForm.notes} onChange={(e) => setEventForm({ ...eventForm, notes: e.currentTarget.value })} />
        <Group justify="flex-end"><Button variant="light" color="grape" onClick={() => void addOccasion()} disabled={!eventForm.label || !eventForm.event_date}>Add occasion</Button></Group>
      </Stack></Paper>
    </Stack>
  </Modal>
}
