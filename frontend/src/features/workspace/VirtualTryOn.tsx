import { useEffect, useRef, useState } from 'react'
import { Alert, Badge, Box, Button, Checkbox, FileInput, Group, Image, Paper, Select, SimpleGrid, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { Camera, ImagePlus, Sparkles } from 'lucide-react'
import './virtual-try-on.css'

export type TryOnGarment = { key: string; itemId: number; variantId?: number; name: string; mediaUrl: string | null; fabricOnly: boolean }
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

export function VirtualTryOn({ customerId, customerName, garments, onBusy }: { customerId: number; customerName: string; garments: TryOnGarment[]; onBusy: (busy: boolean) => void }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [person, setPerson] = useState<File | null>(null)
  const [garmentPhoto, setGarmentPhoto] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [status, setStatus] = useState<{ configured: boolean; message: string } | null>(null)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const [busy, setBusy] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const personUrl = usePhoto(person)
  const uploadedGarmentUrl = usePhoto(garmentPhoto)
  const options = garments.filter((g) => !g.fabricOnly)
  const garment = options.find((g) => g.key === selected) ?? options[0]
  const catalogUrl = garment?.mediaUrl?.startsWith('/media/') ? `${base}${garment.mediaUrl}` : ''
  // Product-level media cannot reliably identify a selected variant.
  const useCatalog = Boolean(catalogUrl && !garment?.variantId)
  const garmentUrl = uploadedGarmentUrl || (useCatalog ? catalogUrl : '')

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${base}/api/try-on/status`, { signal: controller.signal }).then(async (res) => {
      if (!res.ok) throw new Error('Unable to check try-on availability.')
      return res.json() as Promise<{ configured: boolean; message: string }>
    }).then(setStatus).catch(() => { if (!controller.signal.aborted) setStatus({ configured: false, message: 'Unable to connect to virtual try-on. You can continue to customization.' }) })
    return () => { controller.abort(); abort.current?.abort() }
  }, [])

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
      form.append('consent', 'true'); form.append('customer_id', String(customerId)); form.append('item_id', String(garment.itemId))
      if (garment.variantId) form.append('variant_id', String(garment.variantId))
      const response = await fetch(`${base}/api/try-on/generate`, { method: 'POST', body: form, signal: controller.signal })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error?.message || payload.detail || 'Unable to generate preview.')
      if (!payload.image?.startsWith('data:image/')) throw new Error('No preview was returned.')
      setResult(payload.image)
    } catch (e) { setError(e instanceof Error && e.name !== 'AbortError' ? e.message : 'Generation was interrupted or took too long. Please try again.') }
    finally { window.clearTimeout(timer); setBusy(false); onBusy(false) }
  }

  return <Paper withBorder p="lg" className="tryon-studio"><Stack gap="lg">
    <Group justify="space-between"><Group><ThemeIcon color="grape" variant="light" size={48} radius="xl"><Sparkles size={24} /></ThemeIcon><Box><Text size="xs" c="grape" fw={800} tt="uppercase">Your fitting room</Text><Title order={2}>See the look before you customize</Title><Text c="dimmed" size="sm">Preview a finished garment on {customerName}.</Text></Box></Group><Badge color="grape" variant="light">Optional step</Badge></Group>
    {status && !status.configured && <Alert color="yellow" title="Preview setup pending">{status.message} You can explore the photo inputs and continue your order.</Alert>}
    {!options.length ? <Alert color="grape">This order contains fabric only. Virtual try-on needs a finished garment photograph; continue to customization to plan the design.</Alert> : <>
      <Select label="Selected merchandise" data={options.map((g) => ({ value: g.key, label: g.name }))} value={garment?.key ?? null} disabled={busy} onChange={(value) => { setSelected(value); setGarmentPhoto(null); setResult(''); setError('') }} />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Paper withBorder p="md" radius="md"><Stack><Group><Camera size={18} /><Text fw={800}>1. Customer photograph</Text></Group><Box className="tryon-photo">{personUrl ? <Image src={personUrl} alt={`${customerName}'s original photograph`} fit="contain" h={300} /> : <Stack align="center" gap="xs"><Camera size={36} /><Text fw={700}>A clear, front-facing photo</Text><Text size="sm" c="dimmed" ta="center">Show the full body for dresses or the upper body for tops.</Text></Stack>}</Box><FileInput label="Upload customer photo" placeholder="Choose JPEG or PNG" accept="image/jpeg,image/png" value={person} onChange={(file) => choosePhoto(file, 'person')} clearable disabled={busy} /><Text size="xs" c="dimmed">Up to 10 MB. Photos are used for this preview and are not saved to the catalog.</Text></Stack></Paper>
        <Paper withBorder p="md" radius="md"><Stack><Group><ImagePlus size={18} /><Text fw={800}>2. Garment photograph</Text></Group><Box className="tryon-photo">{garmentUrl ? <Image src={garmentUrl} alt={garment?.name} fit="contain" h={300} /> : <Stack align="center" gap="xs"><ImagePlus size={36} /><Text fw={700}>Show the finished garment</Text><Text size="sm" c="dimmed" ta="center">Use the exact colour and variant selected for this order.</Text></Stack>}</Box><FileInput label={useCatalog ? 'Replace catalog photo (optional)' : 'Upload selected garment photo'} placeholder="Choose JPEG or PNG" accept="image/jpeg,image/png" value={garmentPhoto} onChange={(file) => choosePhoto(file, 'garment')} clearable disabled={busy} /><Text size="xs" c="dimmed">A clear flat-lay or on-model image works best. Fabric swatches need a separate design workflow.</Text></Stack></Paper>
      </SimpleGrid>
      <Checkbox label="The customer agrees to send these photos to Google to generate their try-on preview." checked={consent} onChange={(e) => { setConsent(e.currentTarget.checked); setResult('') }} disabled={busy} />
      {error && <Alert color="red" role="alert">{error}</Alert>}
      <Group><Button size="md" color="grape" leftSection={<Sparkles size={18} />} loading={busy} disabled={!status?.configured || !person || !garmentUrl || !consent} onClick={() => void generate()}>Generate try-on preview</Button><Text size="sm" c="dimmed" aria-live="polite">{busy ? 'Creating your preview. This can take up to two minutes…' : 'A visual preview; measurements still guide tailoring.'}</Text></Group>
      {result && <Paper withBorder p="md"><Stack><Group justify="space-between"><Title order={3}>Your look</Title><Button component="a" href={result} download="boutiqueos-try-on.png" variant="light" color="grape">Download preview</Button></Group><SimpleGrid cols={{ base: 1, sm: 2 }}><Stack><Text fw={700}>Original</Text><Image src={personUrl} alt="Original customer photograph" fit="contain" h={420} /></Stack><Stack><Text fw={700}>AI try-on · {garment?.name}</Text><Image src={result} alt={`AI preview of ${customerName} wearing ${garment?.name}`} fit="contain" h={420} /></Stack></SimpleGrid><Text size="sm" c="dimmed">AI may change details of the garment or body. This preview does not predict size or fit.</Text></Stack></Paper>}
    </>}
  </Stack></Paper>
}
