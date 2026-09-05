import { useEffect, useMemo, useState } from 'react'
import { ActionIcon, Alert, Badge, Box, Button, Card, Checkbox, Group, Paper, Select, Stack, Text, TextInput, ThemeIcon, Title } from '@mantine/core'
import { ArrowLeft, ArrowRight, Check, Minus, Package, Plus, Search, ShoppingBag, UserRound, X } from 'lucide-react'
import { api } from '../../api'
import type { Customer, Item, MeasurementProfile, Order } from '../../types'
import './final-ux.css'

type CartLine = { item: Item; quantity: number; requiresTailoring: boolean; measurementProfileId?: number; measurementVersionId?: number }
const steps = ['Customer', 'Items', 'Tailoring', 'Review'] as const

function money(value: string | number) { const n = typeof value === 'string' ? Number(value) : value; return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` }
function quantityLabel(item: Item) { if (item.inventory_type === 'UNIQUE') return item.availability === 'AVAILABLE' ? '1 available' : item.availability.toLowerCase(); if (item.inventory_type === 'YARDAGE') return `${Number(item.quantity_available)} m available`; return `${Number(item.quantity_available)} available` }

function CustomerSearch({ customers, value, onPick }: { customers: Customer[]; value: Customer | null; onPick: (customer: Customer | null) => void }) {
  const [query, setQuery] = useState(value ? `${value.name} · ${value.phone}` : '')
  const [open, setOpen] = useState(false)
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = needle ? customers.filter((c) => `${c.name} ${c.phone} ${c.email ?? ''}`.toLowerCase().includes(needle)) : customers.slice(0, 6)
    return rows.slice(0, 8)
  }, [customers, query])
  return <Box className="smart-search">
    <TextInput size="md" label="Customer" required leftSection={<Search size={16} />} placeholder="Type name, mobile or email..." value={query} onFocus={() => setOpen(true)} onChange={(e) => { setQuery(e.currentTarget.value); setOpen(true); if (value) onPick(null) }} />
    {open && <Box className="smart-search-results">{results.length ? results.map((customer) => <button key={customer.id} type="button" className="smart-search-result" onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(customer); setQuery(`${customer.name} · ${customer.phone}`); setOpen(false) }}><Box><Text fw={800}>{customer.name}</Text><Text size="xs" c="dimmed">{customer.phone}{customer.email ? ` · ${customer.email}` : ''}</Text></Box><UserRound size={17} /></button>) : <Box className="smart-search-empty">No matching customer</Box>}</Box>}
  </Box>
}

function ItemSearch({ items, value, onPick }: { items: Item[]; value: Item | null; onPick: (item: Item | null) => void }) {
  const [query, setQuery] = useState(value?.name ?? '')
  const [open, setOpen] = useState(false)
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const rows = needle ? items.filter((item) => `${item.name} ${item.category} ${item.fabric ?? ''} ${item.color ?? ''} ${item.sku ?? ''}`.toLowerCase().includes(needle)) : items.slice(0, 8)
    return rows.slice(0, 10)
  }, [items, query])
  return <Box className="smart-search">
    <TextInput label="Product" required leftSection={<Search size={16} />} placeholder="Search product, SKU, fabric or colour..." value={query} onFocus={() => setOpen(true)} onChange={(e) => { setQuery(e.currentTarget.value); setOpen(true); if (value) onPick(null) }} />
    {open && <Box className="smart-search-results">{results.length ? results.map((item) => <button key={item.id} type="button" className="smart-search-result" onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(item); setQuery(item.name); setOpen(false) }}><Box><Text fw={800}>{item.name}</Text><Text size="xs" c="dimmed">{item.category}{item.fabric ? ` · ${item.fabric}` : ''}{item.color ? ` · ${item.color}` : ''} · {quantityLabel(item)}</Text></Box><Box style={{ textAlign: 'right' }}><Text fw={800}>{money(item.selling_price)}</Text>{item.sku && <Text size="xs" c="dimmed">{item.sku}</Text>}</Box></button>) : <Box className="smart-search-empty">No matching product</Box>}</Box>}
  </Box>
}

export function GuidedOrdersWorkspaceV2({ customers, orders, onCreated }: { customers: Customer[]; orders: Order[]; onCreated: (order: Order) => void }) {
  const [items, setItems] = useState<Item[]>([])
  const [step, setStep] = useState(0)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [cart, setCart] = useState<CartLine[]>([])
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => { void api.items().then(setItems).catch(() => setError('Unable to load products.')) }, [])
  useEffect(() => {
    if (!customer) return
    let active = true
    void api.customerMeasurementProfiles(customer.id).then((rows) => { if (active) setProfiles(rows) }).catch(() => { if (active) setProfiles([]) })
    return () => { active = false }
  }, [customer])

  const orderableItems = useMemo(() => items.filter((item) => item.inventory_type === 'UNIQUE' ? ['AVAILABLE', 'HELD'].includes(item.availability) : Number(item.quantity_available) > 0), [items])
  const total = cart.reduce((sum, line) => sum + Number(line.item.selling_price) * line.quantity, 0)
  const recentOrders = customer ? orders.filter((order) => order.customer_id === customer.id).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3) : []

  function handleCustomerPick(next: Customer | null) {
    setProfiles([])
    setCustomer(next)
  }

  function addItem() {
    if (!selectedItem) return
    const safeQty = selectedItem.inventory_type === 'UNIQUE' ? 1 : Math.max(1, quantity)
    setCart((current) => {
      const existing = current.find((line) => line.item.id === selectedItem.id)
      if (!existing) return [...current, { item: selectedItem, quantity: safeQty, requiresTailoring: false }]
      return current.map((line) => line.item.id === selectedItem.id ? { ...line, quantity: line.quantity + safeQty } : line)
    })
    setSelectedItem(null); setQuantity(1)
  }

  function chooseMeasurement(itemId: number, profileId: string | null) {
    const profile = profiles.find((row) => row.id === Number(profileId))
    setCart((current) => current.map((line) => line.item.id === itemId ? { ...line, measurementProfileId: profile?.id, measurementVersionId: profile?.latest_version?.id } : line))
  }

  function canContinue() { if (step === 0) return Boolean(customer); if (step === 1) return cart.length > 0; return true }

  async function createOrder() {
    if (!customer || !cart.length) return
    setSubmitting(true); setError(''); setSuccess('')
    try {
      const created = await api.createOrder({ customer_id: customer.id, lines: cart.map((line) => ({ item_id: line.item.id, quantity: String(line.quantity), requires_tailoring: line.requiresTailoring, measurement_profile_id: line.measurementProfileId, measurement_version_id: line.measurementVersionId })) })
      onCreated(created); setSuccess(`Order #${created.id} created.`); setCart([]); handleCustomerPick(null); setStep(0)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create order.') }
    finally { setSubmitting(false) }
  }

  return <Stack gap="lg" className="guided-orders">
    <Group justify="space-between" align="flex-end" className="guided-page-heading"><Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Orders</Title><Text c="dimmed" mt={4}>Search, add, tailor and confirm without wrestling with dropdowns.</Text></Box><Badge variant="light" color="grape" size="lg">{cart.length} items · {money(total)}</Badge></Group>
    {error && <Alert color="red" title="Unable to continue">{error}</Alert>}{success && <Alert color="teal" title="Done">{success}</Alert>}

    <Paper withBorder p="sm" className="wizard-progress"><Group gap="xs" wrap="nowrap">{steps.map((label, index) => <Box key={label} className={`wizard-step ${index === step ? 'active' : ''} ${index < step ? 'complete' : ''}`} onClick={() => index < step && setStep(index)}><ThemeIcon size={30} radius="xl" color="grape" variant={index <= step ? 'filled' : 'light'}>{index < step ? <Check size={14}/> : <Text size="xs" fw={900}>{index + 1}</Text>}</ThemeIcon><Text size="sm" fw={index === step ? 800 : 600} visibleFrom="sm">{label}</Text></Box>)}</Group></Paper>

    {step === 0 && <Paper withBorder p="lg" className="wizard-card"><Stack gap="lg"><Box><Text fw={800} size="lg">Who is this order for?</Text><Text size="sm" c="dimmed">Start typing. Recent customers appear before you search.</Text></Box><CustomerSearch customers={customers} value={customer} onPick={handleCustomerPick} />{customer && <Card withBorder><Group justify="space-between"><Box><Text fw={900}>{customer.name}</Text><Text size="sm" c="dimmed">{customer.phone}</Text></Box><Badge variant="light" color="grape">{recentOrders.length} recent orders</Badge></Group>{recentOrders.length > 0 && <Group gap="xs" mt="sm">{recentOrders.map((order) => <Badge key={order.id} variant="outline" color="gray">#{order.id} · {money(order.total_amount)}</Badge>)}</Group>}</Card>}</Stack></Paper>}

    {step === 1 && <Paper withBorder p="lg" className="wizard-card"><Stack gap="lg"><Box><Text fw={800} size="lg">What are they buying?</Text><Text size="sm" c="dimmed">Search across name, SKU, fabric, colour and category.</Text></Box><ItemSearch items={orderableItems} value={selectedItem} onPick={setSelectedItem} />{selectedItem && <Card withBorder><Group justify="space-between"><Group><ThemeIcon color="grape" variant="light"><Package size={17}/></ThemeIcon><Box><Text fw={800}>{selectedItem.name}</Text><Text size="sm" c="dimmed">{quantityLabel(selectedItem)}</Text></Box></Group><Text fw={900}>{money(selectedItem.selling_price)}</Text></Group><Group justify="space-between" mt="md"><Group gap={0} className="quantity-control"><ActionIcon variant="default" onClick={() => setQuantity((v) => Math.max(1, v - 1))} disabled={selectedItem.inventory_type === 'UNIQUE'}><Minus size={14}/></ActionIcon><Text className="quantity-value">{selectedItem.inventory_type === 'UNIQUE' ? 1 : quantity}</Text><ActionIcon variant="default" onClick={() => setQuantity((v) => v + 1)} disabled={selectedItem.inventory_type === 'UNIQUE'}><Plus size={14}/></ActionIcon></Group><Button color="grape" onClick={addItem} leftSection={<Plus size={15}/>}>Add item</Button></Group></Card>}
      <Stack gap="sm">{cart.length === 0 && <Box className="empty-cart"><ShoppingBag size={28}/><Text fw={700}>No items added yet</Text></Box>}{cart.map((line) => <Card key={line.item.id} withBorder><Group justify="space-between"><Box><Text fw={800}>{line.item.name}</Text><Text size="sm" c="dimmed">Qty {line.quantity} · {line.item.inventory_type}</Text></Box><Group><Text fw={900}>{money(Number(line.item.selling_price) * line.quantity)}</Text><ActionIcon color="red" variant="subtle" onClick={() => setCart((rows) => rows.filter((row) => row.item.id !== line.item.id))}><X size={15}/></ActionIcon></Group></Group></Card>)}</Stack></Stack></Paper>}

    {step === 2 && <Paper withBorder p="lg" className="wizard-card"><Stack gap="lg"><Box><Text fw={800} size="lg">Tailoring & measurements</Text><Text size="sm" c="dimmed">Only ask for tailoring details when the garment needs them.</Text></Box>{cart.map((line) => <Card key={line.item.id} withBorder><Stack gap="sm"><Group justify="space-between"><Box><Text fw={800}>{line.item.name}</Text><Text size="sm" c="dimmed">{line.item.category}</Text></Box><Checkbox label="Requires tailoring" checked={line.requiresTailoring} onChange={(e) => setCart((rows) => rows.map((row) => row.item.id === line.item.id ? { ...row, requiresTailoring: e.currentTarget.checked, measurementProfileId: e.currentTarget.checked ? row.measurementProfileId : undefined, measurementVersionId: e.currentTarget.checked ? row.measurementVersionId : undefined } : row))} /></Group>{line.requiresTailoring && (profiles.length ? <Select label="Measurement profile" placeholder="Use saved measurements" clearable value={line.measurementProfileId?.toString() ?? null} onChange={(value) => chooseMeasurement(line.item.id, value)} data={profiles.map((profile) => ({ value: String(profile.id), label: `${profile.name}${profile.garment_type ? ` · ${profile.garment_type}` : ''}${profile.latest_version ? ` · v${profile.latest_version.version_number}` : ''}` }))} /> : <Alert color="grape" title="Measurements needed" variant="light">No saved measurement profile for this customer yet.</Alert>)}</Stack></Card>)}</Stack></Paper>}

    {step === 3 && <Paper withBorder p="lg" className="wizard-card"><Stack gap="lg"><Box><Text fw={800} size="lg">Review and confirm</Text><Text size="sm" c="dimmed">One final check before BoutiqueOS commits inventory and the order.</Text></Box><Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={800}>Customer</Text><Text fw={900}>{customer?.name}</Text><Text size="sm" c="dimmed">{customer?.phone}</Text></Card>{cart.map((line) => <Card key={line.item.id} withBorder><Group justify="space-between"><Box><Text fw={800}>{line.item.name}</Text><Text size="sm" c="dimmed">Qty {line.quantity}{line.requiresTailoring ? ' · Tailoring' : ''}{line.measurementProfileId ? ' · Measurements linked' : ''}</Text></Box><Text fw={900}>{money(Number(line.item.selling_price) * line.quantity)}</Text></Group></Card>)}<Box className="review-total"><Text size="sm" c="dimmed">Order total</Text><Title order={2}>{money(total)}</Title></Box><Button size="md" color="grape" loading={submitting} onClick={createOrder} leftSection={<Check size={17}/>}>Confirm order</Button></Stack></Paper>}

    <Group justify="space-between" className="wizard-actions"><Button variant="subtle" color="gray" leftSection={<ArrowLeft size={16}/>} disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</Button>{step < 3 && <Button color="grape" rightSection={<ArrowRight size={16}/>} disabled={!canContinue()} onClick={() => setStep((value) => Math.min(3, value + 1))}>Continue</Button>}</Group>
  </Stack>
}
