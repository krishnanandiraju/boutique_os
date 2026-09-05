import { useEffect, useMemo, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { ArrowLeft, ArrowRight, Check, Minus, Package, Plus, Ruler, ShoppingBag, UserRound, X } from 'lucide-react'
import { api } from '../../api'
import type { Customer, Item, MeasurementProfile, Order } from '../../types'

type CartLine = {
  item: Item
  quantity: number
  requiresTailoring: boolean
  measurementProfileId?: number
  measurementVersionId?: number
}

const steps = [
  { label: 'Customer', icon: UserRound },
  { label: 'Items', icon: ShoppingBag },
  { label: 'Tailoring', icon: Ruler },
  { label: 'Review', icon: Check },
]

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function quantityLabel(item: Item) {
  if (item.inventory_type === 'UNIQUE') return item.availability === 'AVAILABLE' ? '1 available' : item.availability.replaceAll('_', ' ').toLowerCase()
  if (item.inventory_type === 'YARDAGE') return `${Number(item.quantity_available).toLocaleString('en-IN')} m available`
  return `${Number(item.quantity_available).toLocaleString('en-IN')} available`
}

export function GuidedOrdersWorkspace({ customers, orders, onCreated }: {
  customers: Customer[]
  orders: Order[]
  onCreated: (order: Order) => void
}) {
  const [items, setItems] = useState<Item[]>([])
  const [step, setStep] = useState(0)
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [itemId, setItemId] = useState<number | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [cart, setCart] = useState<CartLine[]>([])
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    void api.items().then(setItems).catch(() => setError('Unable to load products.'))
  }, [])

  useEffect(() => {
    if (!customerId) {
      setProfiles([])
      return
    }
    void api.customerMeasurementProfiles(customerId).then(setProfiles).catch(() => setProfiles([]))
  }, [customerId])

  const selectedCustomer = customers.find((customer) => customer.id === customerId) ?? null
  const selectedItem = items.find((item) => item.id === itemId) ?? null
  const orderableItems = useMemo(() => items.filter((item) => {
    if (item.inventory_type === 'UNIQUE') return item.availability === 'AVAILABLE' || item.availability === 'HELD'
    return Number(item.quantity_available) > 0
  }), [items])

  const total = cart.reduce((sum, line) => sum + Number(line.item.selling_price) * line.quantity, 0)
  const tailoringLines = cart.filter((line) => line.requiresTailoring)
  const customerOrders = customerId ? orders.filter((order) => order.customer_id === customerId).slice(-3).reverse() : []

  function addItem() {
    if (!selectedItem) return
    setError('')
    const safeQuantity = selectedItem.inventory_type === 'UNIQUE' ? 1 : Math.max(quantity, 1)
    setCart((current) => {
      const existing = current.find((line) => line.item.id === selectedItem.id)
      if (!existing) return [...current, { item: selectedItem, quantity: safeQuantity, requiresTailoring: false }]
      return current.map((line) => line.item.id === selectedItem.id ? { ...line, quantity: line.quantity + safeQuantity } : line)
    })
    setItemId(null)
    setQuantity(1)
  }

  function removeItem(id: number) {
    setCart((current) => current.filter((line) => line.item.id !== id))
  }

  function toggleTailoring(id: number, checked: boolean) {
    setCart((current) => current.map((line) => line.item.id === id ? { ...line, requiresTailoring: checked, measurementProfileId: checked ? line.measurementProfileId : undefined, measurementVersionId: checked ? line.measurementVersionId : undefined } : line))
  }

  function chooseMeasurement(id: number, profileId: string | null) {
    const profile = profiles.find((candidate) => candidate.id === Number(profileId))
    setCart((current) => current.map((line) => line.item.id === id ? {
      ...line,
      measurementProfileId: profile?.id,
      measurementVersionId: profile?.latest_version?.id,
    } : line))
  }

  function canContinue() {
    if (step === 0) return Boolean(customerId)
    if (step === 1) return cart.length > 0
    return true
  }

  async function createOrder() {
    if (!customerId || cart.length === 0) return
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const created = await api.createOrder({
        customer_id: customerId,
        lines: cart.map((line) => ({
          item_id: line.item.id,
          quantity: String(line.quantity),
          requires_tailoring: line.requiresTailoring,
          measurement_profile_id: line.measurementProfileId,
          measurement_version_id: line.measurementVersionId,
        })),
      })
      onCreated(created)
      setSuccess(`Order #${created.id} created successfully.`)
      setCart([])
      setCustomerId(null)
      setStep(0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create order.')
    } finally {
      setSubmitting(false)
    }
  }

  return <Stack gap="lg" className="guided-orders">
    <Group justify="space-between" align="flex-end" className="guided-page-heading">
      <Box>
        <Text size="sm" c="dimmed">Operations</Text>
        <Title order={1}>Orders</Title>
        <Text c="dimmed" mt={4}>A quick guided flow from customer to confirmed order.</Text>
      </Box>
      <Badge variant="light" color="grape" size="lg">{cart.length} {cart.length === 1 ? 'item' : 'items'} · {money(total)}</Badge>
    </Group>

    {error && <Alert color="red" title="Unable to continue">{error}</Alert>}
    {success && <Alert color="teal" title="Done">{success}</Alert>}

    <Paper withBorder p="sm" className="wizard-progress">
      <Group gap="xs" wrap="nowrap" justify="space-between">
        {steps.map((item, index) => {
          const Icon = item.icon
          const active = index === step
          const complete = index < step
          return <Box key={item.label} className={`wizard-step ${active ? 'active' : ''} ${complete ? 'complete' : ''}`} onClick={() => index < step && setStep(index)}>
            <ThemeIcon size={30} radius="xl" variant={active || complete ? 'filled' : 'light'} color="grape">
              {complete ? <Check size={15} /> : <Icon size={15} />}
            </ThemeIcon>
            <Text size="sm" fw={active ? 800 : 600} visibleFrom="sm">{item.label}</Text>
          </Box>
        })}
      </Group>
    </Paper>

    {step === 0 && <Paper withBorder p="lg" className="wizard-card">
      <Stack gap="lg">
        <Box><Text fw={800} size="lg">Who is this order for?</Text><Text size="sm" c="dimmed">Search by customer name or mobile number.</Text></Box>
        <Select
          size="md"
          searchable
          clearable
          placeholder="Search or select customer"
          value={customerId?.toString() ?? null}
          onChange={(value) => setCustomerId(value ? Number(value) : null)}
          data={customers.map((customer) => ({ value: String(customer.id), label: `${customer.name} · ${customer.phone}` }))}
        />
        {selectedCustomer && <Card withBorder padding="md" className="selected-customer-card">
          <Group justify="space-between" align="flex-start">
            <Group><ThemeIcon size={42} radius="xl" variant="light" color="grape"><UserRound size={20} /></ThemeIcon><Box><Text fw={800}>{selectedCustomer.name}</Text><Text size="sm" c="dimmed">{selectedCustomer.phone}{selectedCustomer.email ? ` · ${selectedCustomer.email}` : ''}</Text></Box></Group>
            <Badge variant="light" color="gray">{customerOrders.length ? `${customerOrders.length} recent orders` : 'New relationship'}</Badge>
          </Group>
          {customerOrders.length > 0 && <Group gap="xs" mt="md">{customerOrders.map((order) => <Badge key={order.id} variant="outline" color="gray">#{order.id} · {money(order.total_amount)}</Badge>)}</Group>}
        </Card>}
      </Stack>
    </Paper>}

    {step === 1 && <Paper withBorder p="lg" className="wizard-card">
      <Stack gap="lg">
        <Box><Text fw={800} size="lg">What are they buying?</Text><Text size="sm" c="dimmed">Add one or more products. Unique pieces are automatically limited to one.</Text></Box>
        <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md" className="item-entry-grid">
          <Select searchable label="Product" placeholder="Search products" value={itemId?.toString() ?? null} onChange={(value) => setItemId(value ? Number(value) : null)} data={orderableItems.map((item) => ({ value: String(item.id), label: `${item.name} · ${money(item.selling_price)}` }))} />
          <Box>
            <Text size="sm" fw={500} mb={5}>Quantity</Text>
            <Group gap={0} className="quantity-control">
              <ActionIcon variant="default" size={36} onClick={() => setQuantity((value) => Math.max(1, value - 1))} disabled={selectedItem?.inventory_type === 'UNIQUE'}><Minus size={15} /></ActionIcon>
              <Text ta="center" fw={700} className="quantity-value">{selectedItem?.inventory_type === 'UNIQUE' ? 1 : quantity}</Text>
              <ActionIcon variant="default" size={36} onClick={() => setQuantity((value) => value + 1)} disabled={selectedItem?.inventory_type === 'UNIQUE'}><Plus size={15} /></ActionIcon>
            </Group>
          </Box>
          <Button mt={{ base: 0, md: 25 }} color="grape" leftSection={<Plus size={16} />} onClick={addItem} disabled={!selectedItem}>Add item</Button>
        </SimpleGrid>

        {selectedItem && <Card withBorder padding="sm" className="product-preview"><Group justify="space-between"><Group><ThemeIcon variant="light" color="grape" size={44}><Package size={20} /></ThemeIcon><Box><Text fw={800}>{selectedItem.name}</Text><Text size="sm" c="dimmed">{selectedItem.inventory_type} · {quantityLabel(selectedItem)}</Text></Box></Group><Text fw={800}>{money(selectedItem.selling_price)}</Text></Group></Card>}

        <Stack gap="sm">
          {cart.length === 0 && <Box className="empty-cart"><ShoppingBag size={28} /><Text fw={700}>No items yet</Text><Text size="sm" c="dimmed">Search and add the first product.</Text></Box>}
          {cart.map((line) => <Card key={line.item.id} withBorder padding="md" className="cart-line"><Group justify="space-between" align="center" wrap="nowrap"><Group wrap="nowrap"><ThemeIcon variant="light" color="grape"><Package size={17} /></ThemeIcon><Box><Text fw={800}>{line.item.name}</Text><Text size="sm" c="dimmed">{line.item.inventory_type} · Qty {line.quantity}</Text></Box></Group><Group wrap="nowrap"><Text fw={800}>{money(Number(line.item.selling_price) * line.quantity)}</Text><ActionIcon variant="subtle" color="red" onClick={() => removeItem(line.item.id)} aria-label={`Remove ${line.item.name}`}><X size={16} /></ActionIcon></Group></Group></Card>)}
        </Stack>
      </Stack>
    </Paper>}

    {step === 2 && <Paper withBorder p="lg" className="wizard-card">
      <Stack gap="lg">
        <Box><Text fw={800} size="lg">Does anything need stitching?</Text><Text size="sm" c="dimmed">Only show tailoring and measurement choices when they matter.</Text></Box>
        {cart.map((line) => <Card key={line.item.id} withBorder padding="md" className="tailoring-line">
          <Stack gap="sm">
            <Group justify="space-between"><Box><Text fw={800}>{line.item.name}</Text><Text size="sm" c="dimmed">{line.item.category}</Text></Box><Checkbox label="Requires tailoring" checked={line.requiresTailoring} onChange={(event) => toggleTailoring(line.item.id, event.currentTarget.checked)} /></Group>
            {line.requiresTailoring && <Box className="tailoring-options">
              {profiles.length ? <Select label="Measurement profile" placeholder="Choose existing measurements" clearable value={line.measurementProfileId?.toString() ?? null} onChange={(value) => chooseMeasurement(line.item.id, value)} data={profiles.map((profile) => ({ value: String(profile.id), label: `${profile.name}${profile.garment_type ? ` · ${profile.garment_type.toLowerCase()}` : ''}${profile.latest_version ? ` · v${profile.latest_version.version_number}` : ''}` }))} /> : <Alert color="grape" variant="light" title="Measurements needed">This customer has no saved measurement profile yet. You can create one from the Measurements workspace.</Alert>}
            </Box>}
          </Stack>
        </Card>)}
        {tailoringLines.length === 0 && <Alert color="gray" variant="light">No tailoring selected. You can continue directly to review.</Alert>}
      </Stack>
    </Paper>}

    {step === 3 && <Paper withBorder p="lg" className="wizard-card review-card">
      <Stack gap="lg">
        <Box><Text fw={800} size="lg">Review and confirm</Text><Text size="sm" c="dimmed">A clean final check before inventory and order records are committed.</Text></Box>
        <Card withBorder padding="md"><Group justify="space-between"><Box><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Customer</Text><Text fw={800}>{selectedCustomer?.name}</Text><Text size="sm" c="dimmed">{selectedCustomer?.phone}</Text></Box><Button variant="subtle" color="gray" onClick={() => setStep(0)}>Change</Button></Group></Card>
        <Stack gap="xs">{cart.map((line) => <Card key={line.item.id} withBorder padding="sm"><Group justify="space-between" wrap="nowrap"><Box><Text fw={700}>{line.item.name}</Text><Text size="sm" c="dimmed">Qty {line.quantity}{line.requiresTailoring ? ' · Tailoring' : ''}{line.measurementProfileId ? ' · Measurements linked' : ''}</Text></Box><Text fw={800}>{money(Number(line.item.selling_price) * line.quantity)}</Text></Group></Card>)}</Stack>
        <Box className="review-total"><Text size="sm" c="dimmed">Order total</Text><Title order={2}>{money(total)}</Title></Box>
        <Button size="md" color="grape" leftSection={<Check size={18} />} loading={submitting} onClick={createOrder}>Confirm order</Button>
      </Stack>
    </Paper>}

    <Group justify="space-between" className="wizard-actions">
      <Button variant="subtle" color="gray" leftSection={<ArrowLeft size={16} />} disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</Button>
      {step < steps.length - 1 && <Button color="grape" rightSection={<ArrowRight size={16} />} disabled={!canContinue()} onClick={() => setStep((value) => Math.min(steps.length - 1, value + 1))}>Continue</Button>}
    </Group>
  </Stack>
}
