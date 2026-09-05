import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Checkbox, Group, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { Save } from 'lucide-react'
import { acceptanceApi, type AudienceSegment, type TenantProfile } from '../../acceptanceApi'

const audienceLabels: Record<AudienceSegment, string> = { WOMEN: 'Women', MEN: 'Men', UNISEX: 'Unisex', CHILDREN: 'Children' }
const audienceGarments: Record<AudienceSegment, string[]> = {
  WOMEN: ['BLOUSE', 'KURTA', 'BOTTOM', 'DRESS', 'LEHENGA_BLOUSE'],
  MEN: ['SHIRT', 'TROUSER', 'KURTA', 'SUIT'],
  UNISEX: ['KURTA', 'SHIRT', 'TROUSER', 'GENERAL'],
  CHILDREN: ['KIDS_TOP', 'KIDS_BOTTOM', 'DRESS'],
}

export function TenantSettingsPanel() {
  const [profile, setProfile] = useState<TenantProfile | null>(null)
  const [audiences, setAudiences] = useState<AudienceSegment[]>([])
  const [defaultAudience, setDefaultAudience] = useState<AudienceSegment>('WOMEN')
  const [garmentTypes, setGarmentTypes] = useState<string[]>([])
  const [customGarments, setCustomGarments] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    void acceptanceApi.tenantProfile().then((result) => {
      setProfile(result); setAudiences(result.supported_audiences); setDefaultAudience(result.default_audience); setGarmentTypes(result.garment_types)
    }).catch((err) => setError(err instanceof Error ? err.message : 'Unable to load boutique settings.'))
  }, [])

  const suggested = useMemo(() => Array.from(new Set(audiences.flatMap((audience) => audienceGarments[audience]))).sort(), [audiences])

  function toggleAudience(audience: AudienceSegment, checked: boolean) {
    setAudiences((current) => {
      const next = checked ? Array.from(new Set([...current, audience])) : current.filter((value) => value !== audience)
      if (!next.length) return current
      if (!next.includes(defaultAudience)) setDefaultAudience(next[0])
      return next
    })
    if (checked) setGarmentTypes((current) => Array.from(new Set([...current, ...audienceGarments[audience]])).sort())
  }

  async function save() {
    if (!audiences.length) return
    setSaving(true); setError(''); setMessage('')
    try {
      const custom = customGarments.split(',').map((value) => value.trim().toUpperCase()).filter(Boolean)
      const saved = await acceptanceApi.saveTenantProfile({ supported_audiences: audiences, default_audience: defaultAudience, garment_types: Array.from(new Set([...garmentTypes, ...custom])).sort() })
      setProfile(saved); setAudiences(saved.supported_audiences); setDefaultAudience(saved.default_audience); setGarmentTypes(saved.garment_types); setCustomGarments(''); setMessage('Boutique scope saved.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save boutique settings.') } finally { setSaving(false) }
  }

  return <Paper withBorder p="lg">
    <Stack gap="md">
      <Group justify="space-between"><div><Title order={3}>Merchandise & measurement scope</Title><Text size="sm" c="dimmed">Configure what this tenant sells. BoutiqueOS does not assume every tenant is women-only.</Text></div><Text size="xs" c="dimmed">Tenant #{profile?.merchant_id ?? 1}</Text></Group>
      {error && <Alert color="red">{error}</Alert>}{message && <Alert color="teal">{message}</Alert>}
      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }}>{(Object.keys(audienceLabels) as AudienceSegment[]).map((audience) => <Checkbox key={audience} label={audienceLabels[audience]} checked={audiences.includes(audience)} onChange={(event) => toggleAudience(audience, event.currentTarget.checked)} />)}</SimpleGrid>
      <Select label="Default merchandise audience" value={defaultAudience} data={audiences.map((audience) => ({ value: audience, label: audienceLabels[audience] }))} onChange={(value) => value && setDefaultAudience(value as AudienceSegment)} />
      <div><Text fw={700} size="sm" mb={6}>Garment types enabled for measurement profiles</Text><Group gap="xs">{suggested.map((garment) => <Checkbox key={garment} label={garment.replaceAll('_', ' ')} checked={garmentTypes.includes(garment)} onChange={(event) => setGarmentTypes((current) => event.currentTarget.checked ? Array.from(new Set([...current, garment])).sort() : current.filter((value) => value !== garment))} />)}</Group></div>
      <TextInput label="Additional garment types" description="Optional, comma-separated. Example: WAISTCOAT, SHERWANI" value={customGarments} onChange={(event) => setCustomGarments(event.currentTarget.value)} />
      <Group justify="flex-end"><Button color="grape" leftSection={<Save size={16} />} loading={saving} disabled={!audiences.length} onClick={() => void save()}>Save tenant scope</Button></Group>
    </Stack>
  </Paper>
}
