import { useEffect, useRef, useState } from 'react'
import { Alert, Badge, Box, Button, Checkbox, FileInput, Group, Image, Paper, Select, SimpleGrid, Stack, Text, Textarea, ThemeIcon, Title } from '@mantine/core'
import { Camera, ImagePlus, Sparkles } from 'lucide-react'
import './virtual-try-on.css'
import { customerPhotoUrl } from './demoCustomers'

export type TryOnGarment = { key: string; itemId: number; variantId?: number; name: string; mediaUrl: string | null; fabricOnly: boolean; notes?: string }
const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
function usePhoto(file: File | null) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setUrl(String(reader.result))
    reader.readAsDataURL(file)
    return () => { reader.onload = null; if (reader.readyState === FileReader.LOADING) reader.abort() }
  }, [file])
  return file ? url : ''
}

export function VirtualTryOn({ customerId, customerName, savedPhotoUrl, garments, onBusy, onNotes }: { customerId: number; customerName: string; savedPhotoUrl?: string | null; garments: TryOnGarment[]; onBusy: (busy: boolean) => void; onNotes: (key: string, notes: string) => void }) {
  const savedPhoto = customerPhotoUrl({photo_url: savedPhotoUrl})
  const [loadingSavedPhoto, setLoadingSavedPhoto] = useState(false)
  const [brief, setBrief] = useState('Knee-length straight kurta, round neckline, three-quarter sleeves, restrained trim.')
  const [selected, setSelected] = useState<string | null>(null)
  const [person, setPerson] = useState<File | null>(null)
  const [garmentPhoto, setGarmentPhoto] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [category, setCategory] = useState<string | null>(null)
  const [photoType, setPhotoType] = useState<string | null>('flat-lay')
  const [status, setStatus] = useState<{ configured: boolean; design_configured?: boolean; provider?: string; message: string } | null>(null)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const personUrl = usePhoto(person)
  const uploadedGarmentUrl = usePhoto(garmentPhoto)
  const options = garments
  const garment = options.find((g) => g.key === selected) ?? options[0]
  const isDesign = Boolean(garment?.fabricOnly)
  const garmentCategory = category || (/dress|gown|lehenga|saree/i.test(garment?.name || '') ? 'one-pieces' : 'tops')
  const available = isDesign ? status?.design_configured : status?.configured
  const catalogUrl = garment?.mediaUrl?.startsWith('/media/') ? `${base}${garment.mediaUrl}` : ''
  // Product-level media cannot reliably identify a selected variant.
  const useCatalog = Boolean(catalogUrl && !garment?.variantId)
  const garmentUrl = uploadedGarmentUrl || (useCatalog ? catalogUrl : '')

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${base}/api/try-on/status`, { signal: controller.signal }).then(async (res) => {
      if (!res.ok) throw new Error('Unable to check try-on availability.')
      return res.json() as Promise<{ configured: boolean; design_configured?: boolean; provider?: string; message: string }>
    }).then(setStatus).catch(() => { if (!controller.signal.aborted) setStatus({ configured: false, message: 'Unable to connect to virtual try-on. You can continue to customization.' }) })
    return () => { controller.abort(); abort.current?.abort() }
  }, [])

  useEffect(() => {
    if (!savedPhoto) return
    const controller = new AbortController()
    void fetch(savedPhoto, {signal: controller.signal}).then(async (response) => {
      if (!response.ok) throw new Error('Photo unavailable')
      const blob = await response.blob()
      if (!controller.signal.aborted) setPerson(new File([blob], 'customer-photo.png', {type: blob.type || 'image/png'}))
    }).catch(() => { /* An upload remains available if the stored photo cannot load. */ })
    return () => controller.abort()
  }, [savedPhoto])

  async function loadSavedPhoto() {
    if (!savedPhoto) return
    setLoadingSavedPhoto(true); setError('')
    try {
      const response = await fetch(savedPhoto)
      if (!response.ok) throw new Error('Unable to load the customer photograph.')
      choosePhoto(new File([await response.blob()], 'customer-photo.png', { type: 'image/png' }), 'person')
    } catch { setError('Unable to load the customer photograph. You can upload a photograph instead.') }
    finally { setLoadingSavedPhoto(false) }
  }

  function choosePhoto(file: File | null, kind: 'person' | 'garment') {
    setResult(''); setError('')
    if (file && (!['image/jpeg', 'image/png'].includes(file.type) || file.size > 10 * 1024 * 1024)) {
      setError('Choose a JPEG or PNG photograph smaller than 10 MB.')
      return
    }
    if (kind === 'person') { setPerson(file); setConsent(false) } else setGarmentPhoto(file)
  }

  async function generate() {
    if (!person || !garment || !consent) return
    setBusy(true); onBusy(true); setError(''); setResult('')
    const controller = new AbortController(); abort.current = controller
    const timer = window.setTimeout(() => controller.abort(), 135_000)
    try {
      let clothing: Blob | null = garmentPhoto
      if (!clothing && useCatalog) {
        const photo = await fetch(catalogUrl, { signal: controller.signal })
        if (!photo.ok) throw new Error('The catalog photograph could not be loaded. Upload a garment photograph instead.')
        clothing = await photo.blob()
      }
      if (!clothing) throw new Error('Upload a photograph of the selected finished garment.')
      const form = new FormData()
      form.append('person', person); form.append('garment', clothing, 'garment.jpg')
      if (isDesign) form.append('brief', brief)
      else { form.append('category', garmentCategory); form.append('photo_type', photoType || 'flat-lay') }
      form.append('consent', 'true'); form.append('customer_id', String(customerId)); form.append('item_id', String(garment.itemId))
      if (garment.variantId) form.append('variant_id', String(garment.variantId))
      const response = await fetch(`${base}/api/try-on/${isDesign ? 'design' : 'generate'}`,  { method: 'POST', body: form, signal: controller.signal })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error?.message || payload.detail || 'Your preview is unavailable right now. Please try later or continue to customization.')
      if (!payload.image?.startsWith('data:image/')) throw new Error('No preview was returned.')
      setResult(payload.image)
    } catch (e) { setError(e instanceof Error && e.name !== 'AbortError' ? e.message : 'Generation was interrupted or took too long. Please try again.') }
    finally { window.clearTimeout(timer); setBusy(false); onBusy(false) }
  }

  return <Paper withBorder p="lg" className="tryon-studio"><Stack gap="lg">
    <Group justify="space-between"><Group><ThemeIcon color="grape" variant="light" size={48} radius="xl"><Sparkles size={24} /></ThemeIcon><Box><Text size="xs" c="grape" fw={800} tt="uppercase">Your fitting room</Text><Title order={2}>See the look before you customize</Title><Text c="dimmed" size="sm">Preview a finished garment on {customerName}.</Text></Box></Group><Badge color="grape" variant="light">Optional step</Badge></Group>
    {status && !available && <Alert color="gray" title={isDesign ? "Design preview is currently unavailable" : "Virtual try-on is currently unavailable"}>You can continue to customization and complete your order.</Alert>}
    {!options.length ? <Alert color="grape">Select merchandise to create a preview.</Alert> : <>
      <Select label="Selected merchandise" data={options.map((g) => ({ value: g.key, label: g.name }))} value={garment?.key ?? null} disabled={busy} onChange={(value) => { setSelected(value); setCategory(null); setGarmentPhoto(null); setResult(''); setError('') }} />
      <Alert color="grape" title={isDesign ? 'Fabric → proposed design' : 'Finished garment → visual try-on'}>{isDesign ? 'An approximate design concept based on this fabric. Colour, motifs, construction and fabric requirements must be confirmed by the tailor.' : 'See how this garment may look on the customer. The image does not establish tightness, ease or alteration amounts; verify with measurements and a fitting.'}</Alert>
      {!isDesign && status?.provider === 'huggingface' && <SimpleGrid cols={{base: 1, sm: 2}}><Select label="Garment type" data={[{value: 'tops', label: 'Top, blouse or kurta'}, {value: 'bottoms', label: 'Trousers or skirt'}, {value: 'one-pieces', label: 'Dress or complete outfit'}]} value={garmentCategory} disabled={busy} onChange={(value) => {setCategory(value); setResult('')}} /><Select label="Garment photograph shows" data={[{value: 'flat-lay', label: 'Garment on its own'}, {value: 'model', label: 'Garment worn by a person'}]} value={photoType} disabled={busy} onChange={(value) => {setPhotoType(value); setResult('')}} /></SimpleGrid>}
      {isDesign && <Textarea label="Proposed design" description="Specify silhouette, neckline, sleeves and length." value={brief} maxLength={1000} disabled={busy} onChange={(e) => { setBrief(e.currentTarget.value); setResult('') }}/>} 
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Paper withBorder p="md" radius="md"><Stack><Group><Camera size={18} /><Text fw={800}>1. Customer photograph</Text></Group><Box className="tryon-photo">{personUrl ? <Image src={personUrl} alt={`${customerName}'s original photograph`} fit="contain" h={300} /> : <Stack align="center" gap="xs"><Camera size={36} /><Text fw={700}>A clear, front-facing photo</Text><Text size="sm" c="dimmed" ta="center">Show the full body for dresses or the upper body for tops.</Text></Stack>}</Box><FileInput label="Upload customer photo" placeholder="Choose JPEG or PNG" accept="image/jpeg,image/png" value={person} onChange={(file) => choosePhoto(file, 'person')} clearable disabled={busy} />{savedPhoto && <Button variant="light" color="grape" disabled={busy} loading={loadingSavedPhoto} onClick={() => void loadSavedPhoto()}>Use saved customer photo</Button>}<Text size="xs" c="dimmed">Up to 10 MB. Photos are used for this preview and are not saved to the catalog.</Text></Stack></Paper>
        <Paper withBorder p="md" radius="md"><Stack><Group><ImagePlus size={18} /><Text fw={800}>2. {isDesign ? 'Fabric photograph' : 'Garment photograph'}</Text></Group><Box className="tryon-photo">{garmentUrl ? <Image src={garmentUrl} alt={garment?.name} fit="contain" h={300} /> : <Stack align="center" gap="xs"><ImagePlus size={36} /><Text fw={700}>Show the finished garment</Text><Text size="sm" c="dimmed" ta="center">Use the exact colour and variant selected for this order.</Text></Stack>}</Box><FileInput label={useCatalog ? 'Replace catalog photo (optional)' : 'Upload selected merchandise photo'} placeholder="Choose JPEG or PNG" accept="image/jpeg,image/png" value={garmentPhoto} onChange={(file) => choosePhoto(file, 'garment')} clearable disabled={busy} /><Text size="xs" c="dimmed">{isDesign ? 'Use a clear fabric photo that shows its weave, colour and pattern.' : 'Use a clear photograph of the finished garment.'}</Text></Stack></Paper>
      </SimpleGrid>
      <Checkbox label="The customer permits these photos to be processed for their virtual try-on preview." checked={consent} onChange={(e) => { setConsent(e.currentTarget.checked); setResult('') }} disabled={busy} />
      {error && <Alert color="red" role="alert">{error}</Alert>}
      <Group><Button size="md" color="grape" leftSection={<Sparkles size={18} />} loading={busy} disabled={!available || !person || !garmentUrl || !consent || (isDesign && brief.trim().length < 3)} onClick={() => void generate()}>{isDesign ? 'Preview proposed design' : 'Preview on me'}</Button><Text size="sm" c="dimmed" aria-live="polite">{busy ? 'Creating your preview. This can take up to two minutes…' : 'A visual preview; measurements still guide tailoring.'}</Text></Group>
      <Textarea label="Adjustments to discuss with the tailor" description="Staff observations: length, sleeves, neckline, ease or construction changes. These are not automatically measured from the preview." value={garment?.notes || ''} maxLength={2000} disabled={busy} onChange={(e) => garment && onNotes(garment.key, e.currentTarget.value)}/>
      {result && <Paper withBorder p="md"><Stack><Group justify="space-between"><Title order={3}>Your look</Title><Button component="a" href={result} download="boutiqueos-try-on.png" variant="light" color="grape">Download preview</Button></Group><SimpleGrid cols={{ base: 1, sm: 2 }}><Stack><Text fw={700}>Original</Text><Image src={personUrl} alt="Original customer photograph" fit="contain" h={420} /></Stack><Stack><Text fw={700}>{isDesign ? 'Approximate design concept' : 'Virtual preview'} · {garment?.name}</Text><Image src={result} alt={`AI preview of ${customerName} wearing ${garment?.name}`} fit="contain" h={420} /></Stack></SimpleGrid><Text size="sm" c="dimmed">AI may change details of the garment or body. This preview does not predict size or fit.</Text></Stack></Paper>}
    </>}
  </Stack></Paper>
}

export function VirtualTryOnAdmin() {
  const [status, setStatus] = useState<{ configured: boolean; design_configured?: boolean; provider?: string; message: string } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${base}/api/try-on/status`, { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('Status unavailable')
      return response.json() as Promise<{ configured: boolean; design_configured?: boolean; provider?: string; message: string }>
    }).then(setStatus).catch(() => {
      if (!controller.signal.aborted) setStatus({ configured: false, message: 'Unable to retrieve backend configuration status.' })
    })
    return () => controller.abort()
  }, [])
  return <Paper withBorder p="lg"><Stack gap="sm"><Group justify="space-between"><Title order={3}>Virtual Try-On integration</Title><Badge color={status?.configured ? 'teal' : 'gray'}>{status?.configured ? 'Configured' : status ? 'Needs attention' : 'Checking'}</Badge></Group><Text size="sm">Provider: {status?.provider === 'huggingface' ? 'FASHN VTON · Hugging Face (free shared GPU)' : 'Google Cloud · Virtual Try-On'} · Fabric concepts: Google Gemini</Text><Text size="sm">Fabric concepts: {status?.design_configured ? 'Configured' : 'Needs setup'}</Text><Text size="sm" c="dimmed">{status?.message || 'Checking backend configuration…'}</Text><Text size="xs" c="dimmed">{status?.provider === 'huggingface' ? 'Free shared GPU allowance; queues and daily limits apply. No paid fallback is enabled. Readiness does not guarantee provider availability.' : 'Project, authentication, billing and model access are configured on the backend. Credential discovery does not verify billing or model access.'}</Text></Stack></Paper>
}
