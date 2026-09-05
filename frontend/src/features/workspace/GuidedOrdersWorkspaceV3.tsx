import { useEffect, useMemo, useState } from 'react'
import { ActionIcon, Alert, Badge, Box, Button, Card, Checkbox, Group, Paper, Select, Stack, Text, TextInput, ThemeIcon, Title } from '@mantine/core'
import { ArrowLeft, ArrowRight, Check, Minus, Plus, Search, ShoppingBag, UserRound, X } from 'lucide-react'
import { acceptanceApi, type ProductView, type VariantView } from '../../acceptanceApi'
import { api } from '../../api'
import type { Customer, MeasurementProfile, Order } from '../../types'
import './acceptance-v3.css'

type Sellable = { product: ProductView; variant: VariantView | null }
type CartLine = { sellable: Sellable; quantity: number; requiresTailoring: boolean; measurementProfileId?: number; measurementVersionId?: number }
const steps = ['Customer', 'Items', 'Tailoring', 'Review'] as const

function money(value: string | number) { const n = typeof value === 'string' ? Number(value) : value; return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` }
function priceOf(line: Sellable) { return Number(line.variant?.selling_price ?? line.product.selling_price) }
function availableOf(line: Sellable) { return Number(line.variant?.quantity_available ?? line.product.quantity_available) }
function sellableKey(line: Sellable) { return `${line.product.id}:${line.variant?.id ?? 'base'}` }

function CustomerSearch({ customers, value, onPick }: { customers: Customer[]; value: Customer | null; onPick: (customer: Customer | null) => void }) {
  const [query, setQuery] = useState(value ? `${value.name} · ${value.phone}` : '')
  const [open, setOpen] = useState(false)
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (needle ? customers.filter((customer) => `${customer.name} ${customer.phone} ${customer.email ?? ''}`.toLowerCase().includes(needle)) : customers).slice(0, 8)
  }, [customers, query])
  return <Box className="v3-smart-search"><TextInput size="md" label="Customer" required leftSection={<Search size={16} />} placeholder="Type name, mobile or email..." value={query} onFocus={() => setOpen(true)} onChange={(e) => { setQuery(e.currentTarget.value); setOpen(true); if (value) onPick(null) }} />{open && <Box className="v3-search-results">{results.map((customer) => <button type="button" key={customer.id} onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(customer); setQuery(`${customer.name} · ${customer.phone}`); setOpen(false) }}><Box><Text fw={800}>{customer.name}</Text><Text size="xs" c="dimmed">{customer.phone}{customer.email ? ` · ${customer.email}` : ''}</Text></Box><UserRound size={17} /></button>)}{results.length === 0 && <Text size="sm" c="dimmed" p="sm">No matching customer</Text>}</Box>}</Box>
}

function ProductSearch({ products, onPick }: { products: ProductView[]; onPick: (sellable: Sellable) => void }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const sellables = useMemo(() => products.flatMap((product) => product.variants.length ? product.variants.map((variant) => ({ product, variant })) : [{ product, variant: null }]), [products])
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return sellables.filter((row) => {
      if (availableOf(row) <= 0) return false
      const text = `${row.product.name} ${row.product.sku ?? ''} ${row.product.category} ${row.product.fabric ?? ''} ${row.product.color ?? ''} ${row.variant?.name ?? ''} ${row.variant?.sku ?? ''} ${Object.values(row.variant?.option_values ?? {}).join(' ')}`.toLowerCase()
      return !needle || text.includes(needle)
    }).slice(0, 10)
  }, [query, sellables])
  return <Box className="v3-smart-search"><TextInput size="md" label="Add product" leftSection={<Search size={16} />} placeholder="Search product, variant, SKU, fabric, colour..." value={query} onFocus={() => setOpen(true)} onChange={(e) => { setQuery(e.currentTarget.value); setOpen(true) }} />{open && <Box className="v3-search-results">{results.map((row) => <button type="button" key={sellableKey(row)} onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(row); setQuery(''); setOpen(false) }}><Box><Text fw={800}>{row.product.name}{row.variant ? ` · ${row.variant.name}` : ''}</Text><Text size="xs" c="dimmed">{row.variant?.sku || row.product.sku || 'No SKU'} · {row.product.category} · {availableOf(row)} {row.product.inventory_type === 'YARDAGE' ? 'm' : 'available'}</Text></Box><Text fw={800}>{money(priceOf(row))}</Text></button>)}{results.length === 0 && <Text size="sm" c="dimmed" p="sm">No matching sellable product</Text>}</Box>}</Box>
}

export function GuidedOrdersWorkspaceV3({ customers, orders, onCreated }: { customers: Customer[]; orders: Order[]; onCreated: () => void }) {
  const [products, setProducts] = useState<ProductView[]>([])
  const [step, setStep] = useState(0)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [cart, setCart] = useState<CartLine[]>([])
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { void acceptanceApi.products().then(setProducts).catch(() => setError('Unable to load products.')) }, [])
  useEffect(() => {
    if (!customer) return
    let active = true
    void api.customerMeasurementProfiles(customer.id).then((rows) => { if (active) setProfiles(rows) }).catch(() => { if (active) setProfiles([]) })
    return () => { active = false }
  }, [customer])

  const total = cart.reduce((sum, line) => sum + priceOf(line.sellable) * line.quantity, 0)
  const recentOrders = customer ? orders.filter((order) => order.customer_id === customer.id).slice(0, 3) : []

  function addSellable(sellable: Sellable) {
    setCart((rows) => {
      const key = sellableKey(sellable)
      const existing = rows.find((row) => sellableKey(row.sellable) === key)
      if (existing) return rows.map((row) => sellableKey(row.sellable) === key ? { ...row, quantity: row.sellable.product.inventory_type === 'UNIQUE' ? 1 : Math.min(row.quantity + 1, availableOf(row.sellable)) } : row)
      return [...rows, { sellable, quantity: 1, requiresTailoring: false }]
    })
  }

  function chooseMeasurement(key: string, profileId: string | null) {
    const profile = profiles.find((row) => row.id === Number(profileId))
    setCart((rows) => rows.map((row) => sellableKey(row.sellable) === key ? { ...row, measurementProfileId: profile?.id, measurementVersionId: profile?.latest_version?.id } : row))
  }

  function canContinue() { if (step === 0) return Boolean(customer); if (step === 1) return cart.length > 0; return true }

  async function createOrder() {
    if (!customer || !cart.length) return
    setSubmitting(true); setError(''); setSuccess('')
    try {
      const created = await acceptanceApi.createVariantAwareOrder({ customer_id: customer.id, lines: cart.map((line) => ({ item_id: line.sellable.product.id, variant_id: line.sellable.variant?.id, quantity: String(line.quantity), requires_tailoring: line.requiresTailoring, measurement_profile_id: line.measurementProfileId, measurement_version_id: line.measurementVersionId })) })
      setSuccess(`Order #${created.id} created.`); setCart([]); setCustomer(null); setProfiles([]); setStep(0); onCreated()
      setProducts(await acceptanceApi.products())
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create order.') } finally { setSubmitting(false) }
  }

  return <Stack gap="lg" className="v3-orders">
    <Group justify="space-between" align="flex-end" className="v3-page-heading"><Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Orders</Title><Text c="dimmed" mt={4}>Search the exact customer and exact sellable variant, then confirm.</Text></Box><Badge variant="light" color="grape" size="lg">{cart.length} lines · {money(total)}</Badge></Group>
    {error && <Alert color="red" title="Unable to continue">{error}</Alert>}{success && <Alert color="teal" title="Done">{success}</Alert>}
    <Paper withBorder p="sm" className="v3-wizard-progress"><Group gap="xs" wrap="nowrap">{steps.map((label, index) => <Box key={label} className={index === step ? 'active' : index < step ? 'done' : ''} onClick={() => index < step && setStep(index)}><ThemeIcon size={30} radius="xl" color="grape" variant={index <= step ? 'filled' : 'light'}>{index < step ? <Check size={14}/> : <Text size="xs" fw={900}>{index + 1}</Text>}</ThemeIcon><Text size="sm" fw={index === step ? 800 : 600} visibleFrom="sm">{label}</Text></Box>)}</Group></Paper>

    {step === 0 && <Paper withBorder p="lg"><Stack><Text fw={800} size="lg">Who is this order for?</Text><CustomerSearch customers={customers} value={customer} onPick={(value) => { setCustomer(value); if (!value) setProfiles([]) }} />{customer && <Card withBorder><Group justify="space-between"><Box><Text fw={900}>{customer.name}</Text><Text size="sm" c="dimmed">{customer.phone}</Text></Box><Badge color="grape" variant="light">{recentOrders.length} recent orders</Badge></Group></Card>}</Stack></Paper>}

    {step === 1 && <Paper withBorder p="lg"><Stack><Text fw={800} size="lg">What are they buying?</Text><ProductSearch products={products} onPick={addSellable} />{cart.length === 0 && <Box className="v3-empty-cart"><ShoppingBag size={28}/><Text fw={700}>No items yet</Text><Text size="sm" c="dimmed">Search by product, variant, SKU, fabric or colour.</Text></Box>}{cart.map((line) => { const key = sellableKey(line.sellable); const max = Math.max(1, availableOf(line.sellable)); return <Card key={key} withBorder><Group justify="space-between" align="center"><Box><Text fw={800}>{line.sellable.product.name}{line.sellable.variant ? ` · ${line.sellable.variant.name}` : ''}</Text><Text size="sm" c="dimmed">{line.sellable.variant?.sku || line.sellable.product.sku || 'No SKU'} · {line.sellable.product.inventory_type}</Text></Box><Group><Group gap={0}><ActionIcon variant="default" disabled={line.sellable.product.inventory_type === 'UNIQUE'} onClick={() => setCart((rows) => rows.map((row) => sellableKey(row.sellable) === key ? { ...row, quantity: Math.max(1, row.quantity - 1) } : row))}><Minus size={14}/></ActionIcon><Text w={42} ta="center" fw={800}>{line.quantity}</Text><ActionIcon variant="default" disabled={line.sellable.product.inventory_type === 'UNIQUE' || line.quantity >= max} onClick={() => setCart((rows) => rows.map((row) => sellableKey(row.sellable) === key ? { ...row, quantity: Math.min(max, row.quantity + 1) } : row))}><Plus size={14}/></ActionIcon></Group><Text fw={900} w={90} ta="right">{money(priceOf(line.sellable) * line.quantity)}</Text><ActionIcon color="red" variant="subtle" onClick={() => setCart((rows) => rows.filter((row) => sellableKey(row.sellable) !== key))}><X size={15}/></ActionIcon></Group></Group></Card>})}</Stack></Paper>}

    {step === 2 && <Paper withBorder p="lg"><Stack><Text fw={800} size="lg">Tailoring & measurements</Text>{cart.map((line) => { const key = sellableKey(line.sellable); return <Card key={key} withBorder><Stack><Group justify="space-between"><Box><Text fw={800}>{line.sellable.product.name}{line.sellable.variant ? ` · ${line.sellable.variant.name}` : ''}</Text><Text size="sm" c="dimmed">{line.sellable.product.category}</Text></Box><Checkbox label="Requires tailoring" checked={line.requiresTailoring} onChange={(e) => setCart((rows) => rows.map((row) => sellableKey(row.sellable) === key ? { ...row, requiresTailoring: e.currentTarget.checked, measurementProfileId: e.currentTarget.checked ? row.measurementProfileId : undefined, measurementVersionId: e.currentTarget.checked ? row.measurementVersionId : undefined } : row))} /></Group>{line.requiresTailoring && (profiles.length ? <Select label="Measurement profile" placeholder="Use saved measurements" clearable value={line.measurementProfileId?.toString() ?? null} onChange={(value) => chooseMeasurement(key, value)} data={profiles.map((profile) => ({ value: String(profile.id), label: `${profile.name}${profile.garment_type ? ` · ${profile.garment_type}` : ''}${profile.latest_version ? ` · v${profile.latest_version.version_number}` : ''}` }))} /> : <Alert color="grape" variant="light">No saved measurement profile yet.</Alert>)}</Stack></Card>})}</Stack></Paper>}

    {step === 3 && <Paper withBorder p="lg"><Stack><Text fw={800} size="lg">Review and confirm</Text><Card withBorder><Text size="xs" c="dimmed">CUSTOMER</Text><Text fw={900}>{customer?.name}</Text><Text size="sm" c="dimmed">{customer?.phone}</Text></Card>{cart.map((line) => <Card key={sellableKey(line.sellable)} withBorder><Group justify="space-between"><Box><Text fw={800}>{line.sellable.product.name}{line.sellable.variant ? ` · ${line.sellable.variant.name}` : ''}</Text><Text size="sm" c="dimmed">Qty {line.quantity}{line.requiresTailoring ? ' · Tailoring' : ''}{line.measurementProfileId ? ' · Measurements linked' : ''}</Text></Box><Text fw={900}>{money(priceOf(line.sellable) * line.quantity)}</Text></Group></Card>)}<Box className="v3-review-total"><Text size="sm" c="dimmed">Order total</Text><Title order={2}>{money(total)}</Title></Box><Button color="grape" size="md" loading={submitting} leftSection={<Check size={17}/>} onClick={() => void createOrder()}>Confirm order</Button></Stack></Paper>}

    <Group justify="space-between"><Button variant="subtle" color="gray" leftSection={<ArrowLeft size={16}/>} disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</Button>{step < 3 && <Button color="grape" rightSection={<ArrowRight size={16}/>} disabled={!canContinue()} onClick={() => setStep((value) => Math.min(3, value + 1))}>Continue</Button>}</Group>
  </Stack>
}
