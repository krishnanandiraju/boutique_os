import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Badge, Box, Button, Card, Collapse, Group, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { ChevronDown, ChevronUp, History, Ruler } from 'lucide-react'
import { api } from '../../api'
import type { Customer, MeasurementProfile, MeasurementProfileDetail } from '../../types'
import { MeasurementGuide } from './MeasurementGuide'

type GarmentPreset = 'BLOUSE' | 'KURTA' | 'BOTTOM' | 'GENERAL'

const measurementPresets: Record<GarmentPreset, string[]> = {
  BLOUSE: ['bust', 'waist', 'shoulder', 'blouse_length', 'sleeve_length', 'armhole', 'front_neck_depth', 'back_neck_depth'],
  KURTA: ['bust', 'waist', 'hip', 'shoulder', 'kurta_length', 'sleeve_length', 'armhole'],
  BOTTOM: ['waist', 'hip', 'length', 'thigh', 'bottom_opening'],
  GENERAL: [],
}

const fieldLabels: Record<string, string> = {
  bust: 'Bust', waist: 'Waist', hip: 'Hip', shoulder: 'Shoulder', blouse_length: 'Blouse length',
  kurta_length: 'Kurta length', sleeve_length: 'Sleeve length', armhole: 'Armhole',
  front_neck_depth: 'Front neck depth', back_neck_depth: 'Back neck depth', length: 'Length',
  thigh: 'Thigh', bottom_opening: 'Bottom opening',
}

export function VisualMeasurementsWorkspace({ customers }: { customers: Customer[] }) {
  const [customerId, setCustomerId] = useState<number | null>(customers[0]?.id ?? null)
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [profile, setProfile] = useState<MeasurementProfileDetail | null>(null)
  const [profileName, setProfileName] = useState('Self')
  const [garment, setGarment] = useState<GarmentPreset>('BLOUSE')
  const [unit, setUnit] = useState<'INCH' | 'CM'>('INCH')
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const [activeField, setActiveField] = useState<string | null>('bust')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  useEffect(() => {
    if (!customerId && customers[0]) setCustomerId(customers[0].id)
  }, [customers, customerId])

  useEffect(() => {
    if (!customerId) return
    setError('')
    void api.customerMeasurementProfiles(customerId).then(async (result) => {
      setProfiles(result)
      if (result[0]) await loadProfile(result[0].id)
      else resetProfile()
    }).catch((err) => setError(err instanceof Error ? err.message : 'Unable to load measurements'))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId])

  const fields = useMemo(() => measurementPresets[garment], [garment])
  const selectedCustomer = customers.find((customer) => customer.id === customerId)

  function resetProfile() {
    setProfile(null); setProfileName('Self'); setGarment('BLOUSE'); setUnit('INCH'); setValues({}); setNotes(''); setActiveField('bust')
  }

  async function loadProfile(id: number) {
    const detail = await api.measurementProfile(id)
    setProfile(detail); setProfileName(detail.name); setGarment((detail.garment_type as GarmentPreset) || 'GENERAL'); setUnit(detail.unit)
    const latest = detail.latest_version
    setValues(latest ? Object.fromEntries(Object.entries(latest.measurements).map(([key, value]) => [key, String(value)])) : {})
    setNotes(latest?.notes || '')
    setActiveField(measurementPresets[(detail.garment_type as GarmentPreset) || 'GENERAL'][0] || null)
  }

  async function chooseProfile(profileId: string | null) {
    setError(''); setMessage('')
    if (!profileId) return resetProfile()
    try { await loadProfile(Number(profileId)) } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load profile') }
  }

  function changeGarment(value: string | null) {
    const next = (value as GarmentPreset) || 'BLOUSE'
    setGarment(next); setValues({}); setActiveField(measurementPresets[next][0] || null)
  }

  function focusField(field: string) {
    setActiveField(field)
    inputRefs.current[field]?.focus()
  }

  async function saveMeasurements() {
    if (!customerId) return
    const measurementPayload = Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim() !== '').map(([key, value]) => [key, value]))
    if (!Object.keys(measurementPayload).length) { setError('Enter at least one measurement before saving.'); return }
    setSaving(true); setError(''); setMessage('')
    try {
      if (profile) {
        await api.createMeasurementVersion(profile.id, { measurements: measurementPayload, notes: notes || undefined })
        const updated = await api.measurementProfile(profile.id); setProfile(updated)
        setMessage(`Saved measurement version ${updated.latest_version?.version_number ?? ''}`)
      } else {
        const created = await api.createMeasurementProfile(customerId, { name: profileName, garment_type: garment, unit, measurements: measurementPayload, notes: notes || undefined })
        setProfile(created); setProfiles(await api.customerMeasurementProfiles(customerId)); setMessage('Measurement profile created')
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save measurements') }
    finally { setSaving(false) }
  }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end">
      <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Measurements</Title><Text c="dimmed" mt={6}>Take measurements quickly with a garment-specific visual guide.</Text></Box>
      {profile?.versions?.length ? <Button variant="subtle" color="gray" leftSection={<History size={16} />} rightSection={historyOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />} onClick={() => setHistoryOpen((value) => !value)}>History ({profile.versions.length})</Button> : null}
    </Group>

    {error && <Alert color="red" title="Unable to continue">{error}</Alert>}
    {message && <Alert color="teal" title="Saved">{message}</Alert>}

    <Paper withBorder p="lg">
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <Select label="Customer" searchable value={customerId?.toString() ?? null} onChange={(value) => setCustomerId(value ? Number(value) : null)} data={customers.map((customer) => ({ value: String(customer.id), label: `${customer.name} · ${customer.phone}` }))} />
        <Select label="Profile" value={profile?.id.toString() ?? 'new'} onChange={(value) => chooseProfile(value === 'new' ? null : value)} data={[{ value: 'new', label: '+ New profile' }, ...profiles.map((item) => ({ value: String(item.id), label: item.name }))]} />
        <Select label="Garment" value={garment} disabled={Boolean(profile)} onChange={changeGarment} data={[{ value: 'BLOUSE', label: 'Blouse' }, { value: 'KURTA', label: 'Kurta' }, { value: 'BOTTOM', label: 'Bottom' }, { value: 'GENERAL', label: 'General' }]} />
        <Select label="Unit" value={unit} disabled={Boolean(profile)} onChange={(value) => setUnit((value as 'INCH' | 'CM') || 'INCH')} data={[{ value: 'INCH', label: 'Inches' }, { value: 'CM', label: 'Centimetres' }]} />
      </SimpleGrid>
      {!profile && <TextInput label="Profile name" value={profileName} onChange={(event) => setProfileName(event.currentTarget.value)} mt="md" maw={320} />}
    </Paper>

    <Collapse in={historyOpen}>
      <Paper withBorder p="md">
        <Group justify="space-between" mb="sm"><Text fw={800}>Measurement history</Text><Text size="sm" c="dimmed">Past orders keep the version originally used.</Text></Group>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
          {profile?.versions?.slice().reverse().map((version) => <Card key={version.id} withBorder padding="sm"><Group justify="space-between"><Text fw={700}>Version {version.version_number}</Text><Text size="xs" c="dimmed">{new Date(version.created_at).toLocaleDateString()}</Text></Group><Text size="xs" c="dimmed" mt={4}>{Object.keys(version.measurements).length} measurements</Text></Card>)}
        </SimpleGrid>
      </Paper>
    </Collapse>

    <SimpleGrid cols={{ base: 1, lg: 5 }} spacing="lg">
      <Paper withBorder p="lg" className="measurement-form-card" style={{ gridColumn: 'span 3' }}>
        <Group justify="space-between" mb="lg"><Box><Group gap="xs"><Ruler size={17} /><Text size="xs" fw={800} c="grape.6" tt="uppercase">{garment.replace('_', ' ')}</Text></Group><Title order={3}>{selectedCustomer?.name || 'Customer'} measurements</Title></Box>{profile?.latest_version && <Badge variant="light" color="grape">Version {profile.latest_version.version_number}</Badge>}</Group>
        {fields.length ? <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          {fields.map((field, index) => <TextInput key={field} ref={(node) => { inputRefs.current[field] = node }} label={`${index + 1}. ${fieldLabels[field] || field}`} rightSection={<Text size="xs" c="dimmed">{unit === 'INCH' ? 'in' : 'cm'}</Text>} value={values[field] || ''} onFocus={() => setActiveField(field)} onChange={(event) => setValues((current) => ({ ...current, [field]: event.currentTarget.value }))} inputMode="decimal" placeholder="0.0" />)}
        </SimpleGrid> : <Alert color="gray">Choose Blouse, Kurta or Bottom for guided measurement entry.</Alert>}
        <TextInput label="Notes" value={notes} onChange={(event) => setNotes(event.currentTarget.value)} mt="lg" placeholder="Fit, posture or tailoring notes" />
        <Group justify="flex-end" mt="lg"><Button color="grape" loading={saving} onClick={saveMeasurements}>{profile ? 'Save new version' : 'Create measurement profile'}</Button></Group>
      </Paper>
      <Box style={{ gridColumn: 'span 2' }}><MeasurementGuide garment={garment} activeField={activeField} onSelectField={focusField} /></Box>
    </SimpleGrid>
  </Stack>
}
