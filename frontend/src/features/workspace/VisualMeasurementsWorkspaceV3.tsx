import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Badge, Box, Button, Card, Group, Paper, SegmentedControl, Select, SimpleGrid, Stack, Text, TextInput, Title, UnstyledButton } from '@mantine/core'
import { ChevronDown, ChevronUp, History, Ruler } from 'lucide-react'
import { acceptanceApi, type TenantProfile } from '../../acceptanceApi'
import { api } from '../../api'
import type { Customer, MeasurementProfile, MeasurementProfileDetail } from '../../types'
import './acceptance-v3.css'

type View = 'FRONT' | 'BACK'
type Field = { key: string; label: string; hint: string; view: View }

const presets: Record<string, Field[]> = {
  BLOUSE: [
    { key: 'bust', label: 'Bust', hint: 'Around the fullest part', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'blouse_length', label: 'Blouse length', hint: 'Shoulder to desired hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to sleeve end', view: 'FRONT' }, { key: 'armhole', label: 'Armhole', hint: 'Around the armhole', view: 'FRONT' }, { key: 'front_neck_depth', label: 'Front neck depth', hint: 'Shoulder line to front neckline', view: 'FRONT' }, { key: 'back_neck_depth', label: 'Back neck depth', hint: 'Shoulder line to back neckline', view: 'BACK' },
  ],
  KURTA: [
    { key: 'chest_bust', label: 'Chest / bust', hint: 'Around the fullest torso point', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'hip', label: 'Hip', hint: 'Around the fullest hip', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'kurta_length', label: 'Kurta length', hint: 'Shoulder to hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to sleeve end', view: 'FRONT' }, { key: 'armhole', label: 'Armhole', hint: 'Around the armhole', view: 'FRONT' },
  ],
  BOTTOM: [
    { key: 'waist', label: 'Waist', hint: 'Around the waist', view: 'FRONT' }, { key: 'hip', label: 'Hip', hint: 'Around the fullest hip', view: 'FRONT' }, { key: 'length', label: 'Length', hint: 'Waist to hem', view: 'FRONT' }, { key: 'thigh', label: 'Thigh', hint: 'Around upper thigh', view: 'FRONT' }, { key: 'bottom_opening', label: 'Bottom opening', hint: 'Desired leg opening', view: 'FRONT' },
  ],
  DRESS: [
    { key: 'chest_bust', label: 'Chest / bust', hint: 'Around the fullest torso point', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'hip', label: 'Hip', hint: 'Around the fullest hip', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'dress_length', label: 'Dress length', hint: 'Shoulder to hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to sleeve end', view: 'FRONT' },
  ],
  LEHENGA_BLOUSE: [
    { key: 'bust', label: 'Bust', hint: 'Around the fullest part', view: 'FRONT' }, { key: 'underbust', label: 'Underbust', hint: 'Around torso below bust', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'blouse_length', label: 'Blouse length', hint: 'Shoulder to hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to sleeve end', view: 'FRONT' },
  ],
  SHIRT: [
    { key: 'chest', label: 'Chest', hint: 'Around the fullest chest', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'neck', label: 'Neck', hint: 'Around the base of the neck', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'shirt_length', label: 'Shirt length', hint: 'Shoulder to desired hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to cuff', view: 'FRONT' }, { key: 'armhole', label: 'Armhole', hint: 'Around the armhole', view: 'FRONT' },
  ],
  TROUSER: [
    { key: 'waist', label: 'Waist', hint: 'Around the trouser waist', view: 'FRONT' }, { key: 'seat', label: 'Seat / hip', hint: 'Around the fullest seat', view: 'FRONT' }, { key: 'outseam', label: 'Outseam', hint: 'Waist to trouser hem', view: 'FRONT' }, { key: 'inseam', label: 'Inseam', hint: 'Crotch to trouser hem', view: 'FRONT' }, { key: 'thigh', label: 'Thigh', hint: 'Around upper thigh', view: 'FRONT' }, { key: 'knee', label: 'Knee', hint: 'Around knee line', view: 'FRONT' }, { key: 'bottom_opening', label: 'Bottom opening', hint: 'Desired trouser opening', view: 'FRONT' },
  ],
  SUIT: [
    { key: 'chest', label: 'Chest', hint: 'Around the fullest chest', view: 'FRONT' }, { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'jacket_length', label: 'Jacket length', hint: 'Shoulder to jacket hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to cuff', view: 'FRONT' }, { key: 'neck', label: 'Neck', hint: 'Around base of neck', view: 'FRONT' }, { key: 'trouser_waist', label: 'Trouser waist', hint: 'Around trouser waist', view: 'FRONT' }, { key: 'inseam', label: 'Trouser inseam', hint: 'Crotch to hem', view: 'FRONT' },
  ],
  KIDS_TOP: [
    { key: 'chest', label: 'Chest', hint: 'Around the fullest chest', view: 'FRONT' }, { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' }, { key: 'top_length', label: 'Top length', hint: 'Shoulder to hem', view: 'FRONT' }, { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to sleeve end', view: 'FRONT' },
  ],
  KIDS_BOTTOM: [
    { key: 'waist', label: 'Waist', hint: 'Around the waist', view: 'FRONT' }, { key: 'hip', label: 'Hip', hint: 'Around the fullest hip', view: 'FRONT' }, { key: 'length', label: 'Length', hint: 'Waist to hem', view: 'FRONT' },
  ],
}

const linePositions: Record<string, [number, number, number, number]> = {
  bust: [29, 38, 71, 38], chest_bust: [29, 38, 71, 38], chest: [29, 38, 71, 38], underbust: [32, 44, 68, 44], waist: [34, 51, 66, 51], trouser_waist: [34, 51, 66, 51], hip: [31, 62, 69, 62], seat: [31, 62, 69, 62], shoulder: [34, 25, 66, 25], neck: [44, 20, 56, 20], sleeve_length: [66, 27, 80, 47], armhole: [65, 30, 72, 41], blouse_length: [38, 25, 38, 54], kurta_length: [38, 25, 38, 82], dress_length: [38, 25, 38, 91], shirt_length: [38, 25, 38, 74], jacket_length: [38, 25, 38, 76], top_length: [38, 25, 38, 62], length: [39, 51, 39, 91], outseam: [39, 51, 39, 91], inseam: [52, 59, 52, 91], thigh: [34, 67, 50, 67], knee: [35, 78, 50, 78], bottom_opening: [35, 91, 50, 91], front_neck_depth: [50, 24, 50, 34], back_neck_depth: [50, 24, 50, 31],
}

function valuesFromProfile(detail: MeasurementProfileDetail) {
  return detail.latest_version ? Object.fromEntries(Object.entries(detail.latest_version.measurements).map(([key, value]) => [key, String(value)])) : {}
}

function UniversalGuide({ garment, fields, activeField, onPick }: { garment: string; fields: Field[]; activeField: string | null; onPick: (field: Field) => void }) {
  const [view, setView] = useState<View>('FRONT')
  const visible = fields.filter((field) => field.view === view)
  if (!fields.length) return <Paper withBorder p="lg"><Text fw={700}>No visual preset for {garment.replaceAll('_', ' ')}</Text><Text size="sm" c="dimmed">This garment type can still use versioned measurements when a preset is added.</Text></Paper>
  return <Paper withBorder p="lg"><Group justify="space-between"><div><Text fw={800}>Measurement guide</Text><Text size="sm" c="dimmed">A neutral garment diagram; the tenant decides which garment types are enabled.</Text></div><SegmentedControl size="xs" value={view} onChange={(value) => setView(value as View)} data={['FRONT', 'BACK']} /></Group><Box className="v3-measurement-figure"><svg viewBox="0 0 100 100" role="img" aria-label={`${garment} measurement diagram`}><circle cx="50" cy="11" r="7" className="v3-guide-head"/><path d={garment.includes('TROUSER') || garment.includes('BOTTOM') ? 'M38 18 L62 18 L66 48 L61 92 L50 92 L50 50 L48 92 L37 92 L34 48 Z' : 'M38 20 Q50 14 62 20 L76 32 L68 43 L63 36 L66 88 L34 88 L37 36 L32 43 L24 32 Z'} className="v3-guide-body"/>{visible.map((field) => { const pos = linePositions[field.key]; if (!pos) return null; const [x1,y1,x2,y2] = pos; const active = activeField === field.key; return <g key={field.key} className={active ? 'v3-guide-line active' : 'v3-guide-line'}><line x1={x1} y1={y1} x2={x2} y2={y2}/><circle cx={x2} cy={y2} r="2.6"/></g> })}</svg></Box><Stack gap={4}>{fields.map((field, index) => <UnstyledButton key={field.key} className={activeField === field.key ? 'v3-guide-instruction active' : 'v3-guide-instruction'} onClick={() => { onPick(field); setView(field.view) }}><Group gap="sm"><span>{index + 1}</span><div><Text size="sm" fw={700}>{field.label}</Text><Text size="xs" c="dimmed">{field.hint}{field.view === 'BACK' ? ' · Back' : ''}</Text></div></Group></UnstyledButton>)}</Stack></Paper>
}

export function VisualMeasurementsWorkspaceV3({ customers }: { customers: Customer[] }) {
  const [tenant, setTenant] = useState<TenantProfile | null>(null)
  const [customerId, setCustomerId] = useState<number | null>(null)
  const effectiveCustomerId = customerId ?? customers[0]?.id ?? null
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [profile, setProfile] = useState<MeasurementProfileDetail | null>(null)
  const [profileName, setProfileName] = useState('Self')
  const [garment, setGarment] = useState('BLOUSE')
  const [unit, setUnit] = useState<'INCH' | 'CM'>('INCH')
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const [activeField, setActiveField] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  useEffect(() => { void acceptanceApi.tenantProfile().then((result) => { setTenant(result); setGarment((current) => result.garment_types.includes(current) ? current : result.garment_types[0] || current) }).catch(() => undefined) }, [])
  useEffect(() => {
    if (!effectiveCustomerId) return
    let active = true
    void api.customerMeasurementProfiles(effectiveCustomerId).then(async (rows) => {
      if (!active) return; setProfiles(rows)
      if (!rows[0]) { setProfile(null); setValues({}); return }
      const detail = await api.measurementProfile(rows[0].id); if (!active) return
      setProfile(detail); setProfileName(detail.name); setGarment(detail.garment_type || tenant?.garment_types[0] || 'GENERAL'); setUnit(detail.unit); setValues(valuesFromProfile(detail)); setNotes(detail.latest_version?.notes || '')
    }).catch((err) => active && setError(err instanceof Error ? err.message : 'Unable to load measurements.'))
    return () => { active = false }
  }, [effectiveCustomerId, tenant])

  const fields = useMemo(() => presets[garment] ?? [], [garment])
  const garmentOptions = tenant?.garment_types?.length ? tenant.garment_types : ['BLOUSE', 'KURTA', 'BOTTOM', 'GENERAL']

  async function chooseProfile(value: string | null) {
    setMessage(''); setError('')
    if (!value || value === 'new') { setProfile(null); setProfileName('Self'); setValues({}); setNotes(''); setGarment(garmentOptions[0] || 'GENERAL'); return }
    try { const detail = await api.measurementProfile(Number(value)); setProfile(detail); setProfileName(detail.name); setGarment(detail.garment_type || 'GENERAL'); setUnit(detail.unit); setValues(valuesFromProfile(detail)); setNotes(detail.latest_version?.notes || '') } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load profile.') }
  }

  async function save() {
    if (!effectiveCustomerId) return
    const measurements = Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim() !== ''))
    if (!Object.keys(measurements).length) { setError('Enter at least one measurement.'); return }
    setSaving(true); setError(''); setMessage('')
    try {
      if (profile) { await api.createMeasurementVersion(profile.id, { measurements, notes: notes || undefined }); const updated = await api.measurementProfile(profile.id); setProfile(updated); setMessage(`Saved version ${updated.latest_version?.version_number ?? ''}`) }
      else { const created = await api.createMeasurementProfile(effectiveCustomerId, { name: profileName, garment_type: garment, unit, measurements, notes: notes || undefined }); setProfile(created); setProfiles(await api.customerMeasurementProfiles(effectiveCustomerId)); setMessage('Measurement profile created.') }
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save measurements.') } finally { setSaving(false) }
  }

  return <Stack gap="lg"><Group justify="space-between" align="flex-end"><Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Measurements</Title><Text c="dimmed" mt={4}>Garment-specific, versioned measurements for any audience enabled by this boutique.</Text></Box>{profile?.versions?.length ? <Button variant="subtle" color="gray" leftSection={<History size={16}/>} rightSection={historyOpen ? <ChevronUp size={15}/> : <ChevronDown size={15}/>} onClick={() => setHistoryOpen((value) => !value)}>History ({profile.versions.length})</Button> : null}</Group>{error && <Alert color="red">{error}</Alert>}{message && <Alert color="teal">{message}</Alert>}
    <Paper withBorder p="lg"><SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}><Select label="Customer" searchable value={effectiveCustomerId?.toString() ?? null} onChange={(value) => setCustomerId(value ? Number(value) : null)} data={customers.map((customer) => ({ value: String(customer.id), label: `${customer.name} · ${customer.phone}` }))}/><Select label="Profile" value={profile?.id.toString() ?? 'new'} onChange={(value) => void chooseProfile(value)} data={[{ value: 'new', label: '+ New profile' }, ...profiles.map((row) => ({ value: String(row.id), label: `${row.name}${row.garment_type ? ` · ${row.garment_type.replaceAll('_',' ')}` : ''}` }))]}/><Select label="Garment" searchable disabled={Boolean(profile)} value={garment} onChange={(value) => { const next = value || 'GENERAL'; setGarment(next); setValues({}); setActiveField((presets[next] ?? [])[0]?.key ?? null) }} data={garmentOptions.map((value) => ({ value, label: value.replaceAll('_', ' ') }))}/><Select label="Unit" disabled={Boolean(profile)} value={unit} onChange={(value) => setUnit((value as 'INCH'|'CM') || 'INCH')} data={[{ value: 'INCH', label: 'Inches' }, { value: 'CM', label: 'Centimetres' }]}/></SimpleGrid>{!profile && <TextInput mt="md" maw={320} label="Profile name" value={profileName} onChange={(event) => setProfileName(event.currentTarget.value)}/>}</Paper>
    {historyOpen && <Paper withBorder p="md"><SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>{profile?.versions?.slice().reverse().map((version) => <Card key={version.id} withBorder><Group justify="space-between"><Text fw={700}>Version {version.version_number}</Text><Text size="xs" c="dimmed">{new Date(version.created_at).toLocaleDateString('en-IN')}</Text></Group><Text size="xs" c="dimmed">{Object.keys(version.measurements).length} measurements</Text></Card>)}</SimpleGrid></Paper>}
    <SimpleGrid cols={{ base: 1, lg: 5 }} spacing="lg"><Paper withBorder p="lg" style={{ gridColumn: 'span 3' }}><Group gap="xs" mb="md"><Ruler size={17}/><Text fw={800}>{garment.replaceAll('_',' ')} measurements</Text>{profile?.latest_version && <Badge color="grape" variant="light">v{profile.latest_version.version_number}</Badge>}</Group>{fields.length ? <SimpleGrid cols={{ base: 1, sm: 2 }}>{fields.map((field, index) => <TextInput key={field.key} ref={(node) => { inputRefs.current[field.key] = node }} label={`${index + 1}. ${field.label}`} rightSection={<Text size="xs" c="dimmed">{unit === 'INCH' ? 'in' : 'cm'}</Text>} value={values[field.key] || ''} onFocus={() => setActiveField(field.key)} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.currentTarget.value }))} inputMode="decimal" placeholder="0.0"/>)}</SimpleGrid> : <Alert color="gray">No predefined visual template for this garment type yet.</Alert>}<TextInput label="Notes" mt="lg" value={notes} onChange={(event) => setNotes(event.currentTarget.value)} placeholder="Fit, posture or tailoring notes"/><Group justify="flex-end" mt="lg"><Button color="grape" loading={saving} onClick={() => void save()}>{profile ? 'Save new version' : 'Create measurement profile'}</Button></Group></Paper><Box style={{ gridColumn: 'span 2' }}><UniversalGuide garment={garment} fields={fields} activeField={activeField} onPick={(field) => { setActiveField(field.key); inputRefs.current[field.key]?.focus() }}/></Box></SimpleGrid>
  </Stack>
}
