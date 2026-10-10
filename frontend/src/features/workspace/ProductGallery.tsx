import { useEffect, useState } from 'react'
import { Alert, Badge, Button, FileButton, Group, Image, Loader, Modal, Paper, SimpleGrid, Stack, Text } from '@mantine/core'
import { acceptanceApi, absoluteMediaUrl, type MediaAsset, type ProductView } from '../../acceptanceApi'

export function ProductGallery({ product, onClose, onChanged }: { product: ProductView; onClose: () => void; onChanged: () => void }) {
  const [media, setMedia] = useState<MediaAsset[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void acceptanceApi.productMedia(product.id).then((rows) => {
      if (active) { setMedia(rows.filter((m) => m.mime_type.startsWith('image/'))); setLoading(false) }
    }).catch(() => { if (active) { setError('Unable to load product images. Close and try again.'); setLoading(false) } })
    return () => { active = false }
  }, [product.id])
  const current = media.find((m) => m.id === selected) ?? media.find((m) => m.is_primary) ?? media[0]
  const url = (m: MediaAsset) => absoluteMediaUrl(m.url || `/media/${m.storage_key}`) || undefined
  async function update(files?: File[]) {
    setBusy(true); setError('')
    try {
      if (files) {
        for (const file of files) await acceptanceApi.uploadProductImage(product.id, file)
      } else if (current) await acceptanceApi.markPrimaryMedia(product.id, current.id, current.sort_order)
      setMedia((await acceptanceApi.productMedia(product.id)).filter((m) => m.mime_type.startsWith('image/')))
    } catch { setError('Some changes could not be saved. Refresh the gallery before trying again.') }
    finally { onChanged(); setBusy(false) }
  }
  return <Modal opened onClose={onClose} closeOnClickOutside={!busy} closeOnEscape={!busy} withCloseButton={!busy} title={product.name} size="lg" centered><Stack>
    {error && <Alert color="red" role="alert">{error}</Alert>}
    {loading ? <Loader aria-label="Loading product images" /> : current ? <><Image src={url(current)} alt={`${product.name} — ${current.original_filename}`} h={420} fit="contain" radius="md" /><Group justify="space-between"><Text size="sm" c="dimmed">{media.findIndex((m) => m.id === current.id) + 1} of {media.length} images</Text>{current.is_primary ? <Badge color="grape">Cover image</Badge> : <Button variant="light" color="grape" loading={busy} onClick={() => void update()}>Use as cover</Button>}</Group><SimpleGrid cols={{ base: 3, sm: 5 }}>{media.map((m, index) => <Paper component="button" type="button" key={m.id} p={4} withBorder aria-label={`View image ${index + 1} of ${product.name}`} aria-pressed={current.id === m.id} disabled={busy} onClick={() => setSelected(m.id)} style={{ cursor: 'pointer', borderColor: current.id === m.id ? 'var(--mantine-color-grape-6)' : undefined }}><Image src={url(m)} alt="" h={90} fit="cover" radius="sm" loading="lazy" /></Paper>)}</SimpleGrid></> : <Text c="dimmed">Add the first photograph of this product.</Text>}
    <FileButton multiple accept="image/png,image/jpeg,image/webp" onChange={(files) => files.length && void update(files)}>{(props) => <Button {...props} variant="light" color="grape" disabled={loading || busy}>Add more images</Button>}</FileButton>
    <Text size="xs" c="dimmed">Use front, back and detail views of the same product. The cover photo appears in merchandise selection.</Text>
  </Stack></Modal>
}
