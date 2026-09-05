import { useEffect, useMemo, useState } from 'react'
import { ActionIcon, Alert, Badge, Box, Button, Card, FileButton, Group, Image, Modal, NumberInput, Paper, Select, SimpleGrid, Stack, Switch, Text, TextInput, Textarea, Title } from '@mantine/core'
import { Camera, ChevronLeft, ChevronRight, ImagePlus, PackagePlus, Plus, Trash2, X } from 'lucide-react'
import { acceptanceApi, absoluteMediaUrl, type AudienceSegment, type ProductView, type VariantSeed } from '../../acceptanceApi'
import type { InventoryType } from '../../types'
import './acceptance-v3.css'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

type DraftVariant = VariantSeed & { id: string; size: string; colour: string }

type ProductDraft = {
  name: string
  sku: string
  inventory_type: InventoryType
  category: string
  fabric: string
  color: string
  selling_price: string
  cost_price: string
  quantity: string
  audience: AudienceSegment
  collection: string
  season: string
  description: string
}

const initialDraft: ProductDraft = {
  name: '', sku: '', inventory_type: 'UNIQUE', category: '', fabric: '', color: '', selling_price: '', cost_price: '', quantity: '1', audience: 'WOMEN', collection: '', season: '', description: '',
}

function newVariant(): DraftVariant {
  return { id: crypto.randomUUID(), name: '', sku: '', option_values: {}, selling_price: '', cost_price: '', quantity: '0', size: '', colour: '' }
}

export function CatalogWorkspaceV3() {
  const [products, setProducts] = useState<ProductView[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('ALL')
  const [opened, setOpened] = useState(false)
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<ProductDraft>(initialDraft)
  const [hasVariants, setHasVariants] = useState(false)
  const [variants, setVariants] = useState<DraftVariant[]>([newVariant()])
  const [files, setFiles] = useState<File[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function load() {
    void acceptanceApi.products().then(setProducts).catch((err) => setError(err instanceof Error ? err.message : 'Unable to load products.'))
  }
  useEffect(load, [])

  const categories = useMemo(() => ['ALL', ...Array.from(new Set(products.map((product) => product.category))).sort()], [products])
  const filtered = useMemo(() => products.filter((product) => {
    const needle = query.trim().toLowerCase()
    const haystack = `${product.name} ${product.sku ?? ''} ${product.category} ${product.fabric ?? ''} ${product.color ?? ''} ${product.collection ?? ''} ${product.variants.map((variant) => `${variant.name} ${variant.sku ?? ''} ${Object.values(variant.option_values).join(' ')}`).join(' ')}`.toLowerCase()
    return (!needle || haystack.includes(needle)) && (category === 'ALL' || product.category === category)
  }), [products, query, category])

  function closeModal() {
    setOpened(false); setStep(0); setDraft(initialDraft); setHasVariants(false); setVariants([newVariant()]); setFiles([]); setError('')
  }

  function updateVariant(id: string, patch: Partial<DraftVariant>) {
    setVariants((rows) => rows.map((row) => row.id === id ? { ...row, ...patch } : row))
  }

  function validBasics() {
    return Boolean(draft.name.trim() && draft.category.trim() && Number(draft.selling_price) >= 0)
  }

  function validVariants() {
    if (!hasVariants) return true
    return variants.length > 0 && variants.every((variant) => variant.name.trim() && Number(variant.quantity) >= 0)
  }

  async function createProduct() {
    if (!validBasics() || !validVariants()) return
    setSaving(true); setError('')
    try {
      const created = await acceptanceApi.createProduct({
        name: draft.name,
        sku: draft.sku || undefined,
        inventory_type: draft.inventory_type,
        category: draft.category,
        fabric: draft.fabric || undefined,
        color: draft.color || undefined,
        selling_price: draft.selling_price,
        cost_price: draft.cost_price || undefined,
        quantity: hasVariants ? '0' : draft.quantity,
        audience: draft.audience,
        collection: draft.collection || undefined,
        season: draft.season || undefined,
        description: draft.description || undefined,
        variants: hasVariants ? variants.map((variant) => ({
          name: variant.name,
          sku: variant.sku || undefined,
          option_values: { ...(variant.size ? { size: variant.size } : {}), ...(variant.colour ? { colour: variant.colour } : {}) },
          selling_price: variant.selling_price || undefined,
          cost_price: variant.cost_price || undefined,
          quantity: variant.quantity,
        })) : [],
      })

      const uploaded = []
      for (const file of files) uploaded.push(await acceptanceApi.uploadProductImage(created.id, file))
      if (uploaded[0]) await acceptanceApi.markPrimaryMedia(created.id, uploaded[0].id, 0)

      closeModal(); load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create product.')
    } finally {
      setSaving(false)
    }
  }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end" className="v3-page-heading">
      <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Products</Title><Text c="dimmed" mt={4}>Merchandise visually; keep inventory, variants and SKUs underneath.</Text></Box>
      <Button color="grape" leftSection={<PackagePlus size={17} />} onClick={() => setOpened(true)}>Add product</Button>
    </Group>
    {error && <Alert color="red" title="Product setup">{error}</Alert>}
    <TextInput size="md" placeholder="Search product, SKU, fabric, colour, collection or variant..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <Group gap="xs" className="v3-filter-scroll">{categories.map((value) => <Button key={value} size="xs" radius="xl" color="grape" variant={category === value ? 'filled' : 'light'} onClick={() => setCategory(value)}>{value === 'ALL' ? 'All' : value}</Button>)}</Group>

    <Box className="v3-merch-grid">
      {filtered.map((product) => {
        const image = absoluteMediaUrl(product.primary_media_url)
        return <Card key={product.id} withBorder padding={0} radius="lg" className="v3-merch-card">
          <Box className="v3-merch-image-wrap">
            {image ? <Image src={image} alt={product.name} h="100%" fit="cover" /> : <Box className="v3-merch-placeholder"><Camera size={42} strokeWidth={1.3} /><Text size="sm" c="dimmed">Add product photography</Text></Box>}
            <Badge className="v3-stock-badge" color={product.availability === 'AVAILABLE' ? 'teal' : product.availability === 'HELD' ? 'orange' : 'gray'}>{product.availability.replaceAll('_', ' ')}</Badge>
          </Box>
          <Stack p="md" gap="xs">
            <Group justify="space-between" align="flex-start" wrap="nowrap"><Box><Text fw={900} size="lg">{product.name}</Text><Text size="sm" c="dimmed">{[product.fabric, product.color].filter(Boolean).join(' · ') || product.category}</Text></Box><Text fw={900}>{money(product.selling_price)}</Text></Group>
            <Group justify="space-between"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>{product.audience ?? 'UNSPECIFIED'} · {product.inventory_type}</Text><Text size="sm" fw={700}>{product.variants.length ? `${product.variants.length} variants` : product.inventory_type === 'YARDAGE' ? `${Number(product.quantity_available)} m` : `${Number(product.quantity_available)} available`}</Text></Group>
            {product.variants.length > 0 && <Group gap={6}>{product.variants.slice(0, 4).map((variant) => <Badge key={variant.id} variant="light" color="grape">{variant.name} · {Number(variant.quantity_available)}</Badge>)}</Group>}
          </Stack>
        </Card>
      })}
    </Box>

    <Modal opened={opened} onClose={closeModal} title="Add product" size="xl" centered classNames={{ content: 'v3-product-modal' }}>
      <Stack gap="lg">
        <Group gap="xs" className="v3-stepper">{['Product', 'Images', 'Variants & stock', 'Review'].map((label, index) => <button type="button" key={label} className={index === step ? 'active' : index < step ? 'done' : ''} onClick={() => index < step && setStep(index)}><span>{index + 1}</span>{label}</button>)}</Group>

        {step === 0 && <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput label="Product name" required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.currentTarget.value })} />
          <TextInput label="SKU" description="Optional for every product" value={draft.sku} onChange={(e) => setDraft({ ...draft, sku: e.currentTarget.value })} />
          <Select label="Inventory type" value={draft.inventory_type} data={[{ value: 'UNIQUE', label: 'Unique piece' }, { value: 'STOCKED', label: 'Stocked item' }, { value: 'YARDAGE', label: 'Fabric / yardage' }]} onChange={(value) => { const next = (value || 'UNIQUE') as InventoryType; setDraft({ ...draft, inventory_type: next, quantity: next === 'UNIQUE' ? '1' : draft.quantity }); if (next === 'UNIQUE') setHasVariants(false) }} />
          <Select label="Audience" value={draft.audience} data={[{ value: 'WOMEN', label: 'Women' }, { value: 'MEN', label: 'Men' }, { value: 'UNISEX', label: 'Unisex' }, { value: 'CHILDREN', label: 'Children' }]} onChange={(value) => setDraft({ ...draft, audience: (value || 'WOMEN') as AudienceSegment })} />
          <TextInput label="Category" required value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.currentTarget.value })} />
          <TextInput label="Fabric" value={draft.fabric} onChange={(e) => setDraft({ ...draft, fabric: e.currentTarget.value })} />
          <TextInput label="Colour" value={draft.color} onChange={(e) => setDraft({ ...draft, color: e.currentTarget.value })} />
          <TextInput label="Selling price" required type="number" value={draft.selling_price} onChange={(e) => setDraft({ ...draft, selling_price: e.currentTarget.value })} />
          <TextInput label="Cost price" type="number" value={draft.cost_price} onChange={(e) => setDraft({ ...draft, cost_price: e.currentTarget.value })} />
          <TextInput label="Collection" value={draft.collection} onChange={(e) => setDraft({ ...draft, collection: e.currentTarget.value })} />
          <TextInput label="Season" value={draft.season} onChange={(e) => setDraft({ ...draft, season: e.currentTarget.value })} />
          <Textarea label="Description" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.currentTarget.value })} />
        </SimpleGrid>}

        {step === 1 && <Stack>
          <Box><Text fw={800} size="lg">Product photography</Text><Text size="sm" c="dimmed">Add one or more images. The first image becomes the primary catalogue image.</Text></Box>
          <FileButton onChange={(selected) => selected && setFiles((current) => [...current, ...selected])} accept="image/png,image/jpeg,image/webp" multiple><Button variant="light" color="grape" leftSection={<ImagePlus size={17} />}>Add images</Button></FileButton>
          <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }}>{files.map((file, index) => <Paper key={`${file.name}-${index}`} withBorder p="xs" className="v3-upload-tile"><Image src={URL.createObjectURL(file)} h={150} fit="cover" radius="md" /><Group justify="space-between" mt="xs" wrap="nowrap"><Text size="xs" truncate>{file.name}</Text><ActionIcon color="red" variant="subtle" onClick={() => setFiles((rows) => rows.filter((_, i) => i !== index))}><X size={15} /></ActionIcon></Group>{index === 0 && <Badge mt={6} color="grape" variant="light">Primary</Badge>}</Paper>)}</SimpleGrid>
          {files.length === 0 && <Paper withBorder p="xl" className="v3-empty-upload"><Camera size={32} /><Text fw={700}>No image yet</Text><Text size="sm" c="dimmed">You can continue without images and add them later.</Text></Paper>}
        </Stack>}

        {step === 2 && <Stack gap="md">
          <Group justify="space-between"><Box><Text fw={800} size="lg">Variants & opening stock</Text><Text size="sm" c="dimmed">Variants are optional. SKUs remain optional even when variants are used.</Text></Box><Switch label="This product has variants" checked={hasVariants} disabled={draft.inventory_type === 'UNIQUE'} onChange={(e) => setHasVariants(e.currentTarget.checked)} /></Group>
          {!hasVariants ? <NumberInput label={draft.inventory_type === 'YARDAGE' ? 'Opening metres' : 'Opening quantity'} min={0} decimalScale={draft.inventory_type === 'YARDAGE' ? 3 : 0} value={Number(draft.quantity)} onChange={(value) => setDraft({ ...draft, quantity: String(value || 0) })} disabled={draft.inventory_type === 'UNIQUE'} /> : <Stack>
            {variants.map((variant, index) => <Paper key={variant.id} withBorder p="md"><Group justify="space-between" mb="sm"><Text fw={800}>Variant {index + 1}</Text><ActionIcon color="red" variant="subtle" disabled={variants.length === 1} onClick={() => setVariants((rows) => rows.filter((row) => row.id !== variant.id))}><Trash2 size={15} /></ActionIcon></Group><SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}><TextInput label="Variant name" placeholder="Blue / M" required value={variant.name} onChange={(e) => updateVariant(variant.id, { name: e.currentTarget.value })} /><TextInput label="Size" placeholder="M" value={variant.size} onChange={(e) => updateVariant(variant.id, { size: e.currentTarget.value })} /><TextInput label="Colour" placeholder="Blue" value={variant.colour} onChange={(e) => updateVariant(variant.id, { colour: e.currentTarget.value })} /><TextInput label="SKU" description="Optional" value={variant.sku || ''} onChange={(e) => updateVariant(variant.id, { sku: e.currentTarget.value })} /><TextInput label="Variant price" placeholder={draft.selling_price || 'Uses base price'} type="number" value={variant.selling_price || ''} onChange={(e) => updateVariant(variant.id, { selling_price: e.currentTarget.value })} /><NumberInput label={draft.inventory_type === 'YARDAGE' ? 'Metres' : 'Stock'} min={0} decimalScale={draft.inventory_type === 'YARDAGE' ? 3 : 0} value={Number(variant.quantity)} onChange={(value) => updateVariant(variant.id, { quantity: String(value || 0) })} /></SimpleGrid></Paper>)}
            <Button variant="light" color="grape" leftSection={<Plus size={15} />} onClick={() => setVariants((rows) => [...rows, newVariant()])}>Add variant</Button>
          </Stack>}
        </Stack>}

        {step === 3 && <Stack>
          <Title order={3}>Review</Title>
          <Paper withBorder p="md"><SimpleGrid cols={{ base: 1, sm: 2 }}><Box><Text size="xs" c="dimmed">Product</Text><Text fw={800}>{draft.name}</Text></Box><Box><Text size="xs" c="dimmed">Category / audience</Text><Text fw={800}>{draft.category} · {draft.audience}</Text></Box><Box><Text size="xs" c="dimmed">Price</Text><Text fw={800}>{money(draft.selling_price || 0)}</Text></Box><Box><Text size="xs" c="dimmed">Inventory</Text><Text fw={800}>{hasVariants ? `${variants.length} variants` : `${draft.quantity} ${draft.inventory_type === 'YARDAGE' ? 'm' : 'units'}`}</Text></Box><Box><Text size="xs" c="dimmed">Images</Text><Text fw={800}>{files.length}</Text></Box><Box><Text size="xs" c="dimmed">SKU</Text><Text fw={800}>{draft.sku || 'Not required'}</Text></Box></SimpleGrid></Paper>
          {hasVariants && <Paper withBorder p="md"><Text fw={800} mb="sm">Variants</Text>{variants.map((variant) => <Group key={variant.id} justify="space-between"><Text>{variant.name}</Text><Text size="sm" c="dimmed">{variant.sku || 'No SKU'} · stock {variant.quantity}</Text></Group>)}</Paper>}
        </Stack>}

        <Group justify="space-between"><Button variant="subtle" color="gray" leftSection={<ChevronLeft size={16} />} disabled={step === 0 || saving} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</Button>{step < 3 ? <Button color="grape" rightSection={<ChevronRight size={16} />} disabled={(step === 0 && !validBasics()) || (step === 2 && !validVariants())} onClick={() => setStep((value) => Math.min(3, value + 1))}>Continue</Button> : <Button color="grape" loading={saving} leftSection={<PackagePlus size={16} />} onClick={() => void createProduct()}>Create product</Button>}</Group>
      </Stack>
    </Modal>
  </Stack>
}
