import { useState } from 'react'
import { Alert, Button, Group, Image, Modal, SimpleGrid, Stack, Text } from '@mantine/core'
import { acceptanceApi } from '../../acceptanceApi'
import { demoCustomers, loadDemoMeasurements } from './demoCustomers'
import { demoAssetUrl, demoProducts, loadDemoPhotography } from './demoPhotography'
export function DemoPhotography({ onChanged }: { onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function load() {
    setBusy(true); setMessage(''); setError('')
    try { const added = await loadDemoPhotography(await acceptanceApi.products()); setMessage(added ? `Added ${added} demo images. Your merchandise galleries are ready.` : 'Demo galleries are already loaded, or products have their own photography.') }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to load demo images. You can retry safely.') }
    finally { onChanged(); setBusy(false) }
  }
  async function loadMeasurements() {
    setBusy(true); setMessage(''); setError('')
    try { const added = await loadDemoMeasurements(); setMessage(added ? `Added ${added} clearly labelled demo measurement profiles. These values are unverified test data.` : 'Demo measurement profiles already exist, or no matching demo customers were found.') }
    catch { setError('Unable to load all demo profiles. You can retry safely.') }
    finally { setBusy(false) }
  }
  return <><Button variant="light" color="grape" onClick={() => setOpen(true)}>Demo photo library</Button><Modal opened={open} onClose={() => setOpen(false)} closeOnClickOutside={!busy} closeOnEscape={!busy} withCloseButton={!busy} title="Demo photo library" size="lg" centered><Stack>
    <Text size="sm">Original AI-generated demo merchandise: three matching views for each sample product. Loading adds photos to the five named demo products and preserves products with your own photography.</Text>
    <SimpleGrid cols={{ base: 2, sm: 5 }}>{demoProducts.map((p) => <Stack key={p.key} gap={4}><Image src={demoAssetUrl(`${p.key}-front.png`)} alt={p.name} h={140} fit="contain" loading="lazy" /><Text size="xs" ta="center">{p.name}</Text></Stack>)}</SimpleGrid>
    {error && <Alert color="red" role="alert">{error}</Alert>}{message && <Alert color="teal" role="status">{message}</Alert>}
    <Button color="grape" loading={busy} onClick={() => void load()}>Load demo product images</Button>
    <Text fw={700}>Try-on test photographs</Text><Text size="sm" c="dimmed">These are fictional adults. Download a photo and upload it in the virtual try-on step to test the flow.</Text>
    <SimpleGrid cols={{base:1,sm:3}}>{demoCustomers.map((customer) => <Stack key={customer.photo}><Image src={demoAssetUrl(customer.photo)} alt={`Fictional demo portrait for ${customer.name}`} h={240} fit="contain" loading="lazy" /><Text fw={700} ta="center">{customer.name}</Text><Text size="xs" ta="center" c="dimmed">Fictional adult · demo photo</Text><Group justify="center"><Button component="a" href={demoAssetUrl(customer.photo)} download variant="light">Download photo</Button></Group></Stack>)}</SimpleGrid>
    <Alert color="yellow" title="Demo measurements are not verified">The sample measurements are invented test values, not dimensions recovered from these photos. Google's try-on model produces images; it does not measure bodies. Use tape-measured real subjects to evaluate measurement accuracy.</Alert>
    <Button variant="light" color="grape" loading={busy} onClick={() => void loadMeasurements()}>Load labelled demo measurements</Button>
  </Stack></Modal></>
}
