import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Box, Button, Card, Group, Modal, Paper, Select, Stack, Table, Text, TextInput, ThemeIcon, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Check, Layers3, Plus, Scissors, Search, Shirt, Sparkles, UserPlus } from 'lucide-react'
import { api } from '../../api'
import type { Customer, Item, Order, TailoringStage, TailoringTask } from '../../types'
import './final-ux.css'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function visualClass(item: Item) {
  const category = item.category.toLowerCase()
  if (category.includes('fabric')) return 'fabric'
  if (category.includes('saree')) return 'saree'
  if (category.includes('kurta')) return 'kurta'
  if (category.includes('blouse')) return 'blouse'
  if (category.includes('lehenga')) return 'lehenga'
  return ''
}

function ProductVisual({ item }: { item: Item }) {
  const category = item.category.toLowerCase()
  const Icon = category.includes('fabric') ? Layers3 : category.includes('saree') || category.includes('lehenga') ? Sparkles : Shirt
  return <Box className={`merch-visual ${visualClass(item)}`}>
    <Box className="merch-visual-icon"><Icon size={52} strokeWidth={1.45} /></Box>
    <Stack gap={4} style={{ position: 'relative', zIndex: 2, maxWidth: '64%' }}>
      <Badge variant="light" color={item.availability === 'AVAILABLE' ? 'teal' : item.availability === 'HELD' ? 'orange' : 'gray'}>{item.availability.replaceAll('_', ' ')}</Badge>
      <Text size="xs" c="dimmed" tt="uppercase" fw={800}>{item.category}</Text>
    </Stack>
  </Box>
}

export function ProductsWorkspace() {
  const [items, setItems] = useState<Item[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('ALL')
  const [opened, { open, close }] = useDisclosure(false)
  const [form, setForm] = useState({ name: '', inventory_type: 'UNIQUE' as 'UNIQUE' | 'STOCKED' | 'YARDAGE', category: '', selling_price: '', quantity: '1' })
  const [error, setError] = useState('')

  function load() { void api.items().then(setItems).catch(() => setError('Unable to load products.')) }
  useEffect(load, [])

  const categories = useMemo(() => ['ALL', ...Array.from(new Set(items.map((item) => item.category))).sort()], [items])
  const filtered = useMemo(() => items.filter((item) => {
    const matchesQuery = `${item.name} ${item.category} ${item.fabric ?? ''} ${item.color ?? ''} ${item.sku ?? ''}`.toLowerCase().includes(query.toLowerCase())
    return matchesQuery && (category === 'ALL' || item.category === category)
  }), [items, query, category])

  async function createProduct() {
    setError('')
    try {
      await api.addItem({ ...form, quantity: form.inventory_type === 'UNIQUE' ? '1' : form.quantity })
      setForm({ name: '', inventory_type: 'UNIQUE', category: '', selling_price: '', quantity: '1' })
      close(); load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create product.') }
  }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end">
      <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Products</Title><Text c="dimmed" mt={4}>Merchandise first. Inventory detail when you need it.</Text></Box>
      <Button color="grape" leftSection={<Plus size={16} />} onClick={open}>Add product</Button>
    </Group>
    {error && <Alert color="red">{error}</Alert>}
    <TextInput size="md" leftSection={<Search size={17} />} placeholder="Search product, fabric, colour or SKU..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <Box className="merchandising-toolbar">
      {categories.map((value) => <Button key={value} size="xs" radius="xl" variant={category === value ? 'filled' : 'light'} color="grape" onClick={() => setCategory(value)}>{value === 'ALL' ? 'All' : value}</Button>)}
    </Box>
    <Box className="merchandising-grid">
      {filtered.map((item) => <Box key={item.id} className="merch-card">
        <ProductVisual item={item} />
        <Box className="merch-meta">
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Box><Text fw={900} size="lg">{item.name}</Text><Text size="sm" c="dimmed">{[item.fabric, item.color].filter(Boolean).join(' · ') || item.category}</Text></Box>
            <Text fw={900} size="lg">{money(item.selling_price)}</Text>
          </Group>
          <Group justify="space-between" mt="md">
            <Text size="xs" c="dimmed" tt="uppercase" fw={800}>{item.inventory_type}{item.sku ? ` · ${item.sku}` : ''}</Text>
            <Text size="sm" fw={700}>{item.inventory_type === 'YARDAGE' ? `${Number(item.quantity_available)} m` : `${Number(item.quantity_available)} available`}</Text>
          </Group>
        </Box>
      </Box>)}
    </Box>
    <Modal opened={opened} onClose={close} title="Add product" centered>
      <Stack>
        <TextInput label="Product name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} />
        <Select label="Inventory type" data={[{value:'UNIQUE',label:'Unique piece'},{value:'STOCKED',label:'Stocked item'},{value:'YARDAGE',label:'Fabric / yardage'}]} value={form.inventory_type} onChange={(value) => value && setForm({ ...form, inventory_type: value as typeof form.inventory_type })} />
        <TextInput label="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.currentTarget.value })} />
        <TextInput label="Selling price" type="number" value={form.selling_price} onChange={(e) => setForm({ ...form, selling_price: e.currentTarget.value })} />
        {form.inventory_type !== 'UNIQUE' && <TextInput label={form.inventory_type === 'YARDAGE' ? 'Metres' : 'Quantity'} type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.currentTarget.value })} />}
        <Button color="grape" onClick={createProduct} disabled={!form.name || !form.category || !form.selling_price}>Create product</Button>
      </Stack>
    </Modal>
  </Stack>
}

export function CustomersWorkspace({ customers, onCreated }: { customers: Customer[]; onCreated: (customer: Customer) => void }) {
  const [query, setQuery] = useState('')
  const [orders, setOrders] = useState<Order[]>([])
  const [profileCounts, setProfileCounts] = useState<Record<number, number>>({})
  const [opened, { open, close }] = useDisclosure(false)
  const [form, setForm] = useState({ name: '', phone: '', email: '' })
  const [error, setError] = useState('')

  useEffect(() => { void api.orders().then(setOrders).catch(() => undefined) }, [])
  useEffect(() => {
    let active = true
    void Promise.all(customers.map(async (customer) => [customer.id, (await api.customerMeasurementProfiles(customer.id)).length] as const))
      .then((pairs) => { if (active) setProfileCounts(Object.fromEntries(pairs)) })
      .catch(() => undefined)
    return () => { active = false }
  }, [customers])

  const filtered = useMemo(() => customers.filter((customer) => `${customer.name} ${customer.phone} ${customer.email ?? ''}`.toLowerCase().includes(query.toLowerCase())), [customers, query])

  async function createCustomer() {
    setError('')
    try {
      const customer = await api.addCustomer(form)
      onCreated(customer); setForm({ name: '', phone: '', email: '' }); close()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create customer.') }
  }

  function customerOrders(customerId: number) { return orders.filter((order) => order.customer_id === customerId) }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end">
      <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Customers</Title><Text c="dimmed" mt={4}>A compact customer directory; rich boutique context stays attached to each customer.</Text></Box>
      <Button color="grape" leftSection={<UserPlus size={16} />} onClick={open}>New customer</Button>
    </Group>
    {error && <Alert color="red">{error}</Alert>}
    <TextInput size="md" leftSection={<Search size={17} />} placeholder="Search name, phone or email..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <Box className="customer-table-card">
      <Table.ScrollContainer minWidth={880}>
        <Table verticalSpacing="sm" highlightOnHover>
          <Table.Thead><Table.Tr><Table.Th>Customer</Table.Th><Table.Th>Mobile</Table.Th><Table.Th>Email</Table.Th><Table.Th>Measurements</Table.Th><Table.Th>Orders</Table.Th><Table.Th>Open order</Table.Th><Table.Th>Last order</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>{filtered.map((customer) => {
            const rows = customerOrders(customer.id)
            const open = rows.filter((order) => !['DELIVERED', 'CANCELLED'].includes(order.status)).length
            const last = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
            return <Table.Tr key={customer.id}>
              <Table.Td><Text className="customer-row-name">{customer.name}</Text></Table.Td>
              <Table.Td>{customer.phone}</Table.Td>
              <Table.Td><Text size="sm" c={customer.email ? undefined : 'dimmed'}>{customer.email || '—'}</Text></Table.Td>
              <Table.Td><Badge variant="light" color={profileCounts[customer.id] ? 'grape' : 'gray'}>{profileCounts[customer.id] ?? 0}</Badge></Table.Td>
              <Table.Td>{rows.length}</Table.Td>
              <Table.Td>{open ? <Badge color="orange" variant="light">{open} open</Badge> : <Text size="sm" c="dimmed">—</Text>}</Table.Td>
              <Table.Td>{last ? <Stack gap={1}><Text size="sm" fw={700}>#{last.id} · {money(last.total_amount)}</Text><Text size="xs" c="dimmed">{new Date(last.created_at).toLocaleDateString('en-IN')}</Text></Stack> : <Text size="sm" c="dimmed">No orders</Text>}</Table.Td>
            </Table.Tr>
          })}</Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Box>
    <Modal opened={opened} onClose={close} title="New customer" centered>
      <Stack><TextInput label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} /><TextInput label="Mobile" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.currentTarget.value })} /><TextInput label="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.currentTarget.value })} /><Button color="grape" onClick={createCustomer} disabled={!form.name || !form.phone}>Save customer</Button></Stack>
    </Modal>
  </Stack>
}

const stageLabels: Record<TailoringStage, string> = { MEASUREMENT_PENDING: 'Measurements required', CUTTING: 'Cutting', STITCHING: 'Stitching', QC: 'Quality check', TRIAL_SCHEDULED: 'Trial', ALTERATION: 'Alteration', READY: 'Ready for pickup' }
const boardStages: TailoringStage[] = ['MEASUREMENT_PENDING', 'CUTTING', 'STITCHING', 'QC', 'READY']
const nextStages: Partial<Record<TailoringStage, TailoringStage[]>> = { MEASUREMENT_PENDING: ['CUTTING'], CUTTING: ['STITCHING'], STITCHING: ['QC'], QC: ['READY', 'ALTERATION'], ALTERATION: ['STITCHING'], READY: ['ALTERATION'] }

export function TailoringWorkspace() {
  const [tasks, setTasks] = useState<TailoringTask[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  function load() { void api.tailoringTasks().then(setTasks).catch(() => setError('Unable to load tailoring work.')) }
  useEffect(load, [])

  async function move(task: TailoringTask, stage: TailoringStage) {
    setError(''); setNotice('')
    try {
      const result = await api.transitionTailoringTask(task.id, stage)
      if (result.order_became_ready) setNotice(`Order #${result.order_id} is ready for pickup. All tailoring items have passed quality check.`)
      else if (stage === 'READY') setNotice(`${task.item_name} is ready. ${result.remaining_tailoring_items} other tailoring item${result.remaining_tailoring_items === 1 ? '' : 's'} still in progress.`)
      load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to update tailoring task.') }
  }

  async function deliver(task: TailoringTask) {
    setError(''); setNotice('')
    try { await api.updateOrderStatus(task.order_id, 'DELIVERED'); setNotice(`Order #${task.order_id} handed over successfully.`); load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to complete handover.') }
  }

  return <Stack gap="lg">
    <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Tailoring</Title><Text c="dimmed" mt={4}>Move each garment through measurement readiness, production, quality check and customer handover.</Text></Box>
    {error && <Alert color="red" title="Unable to update tailoring">{error}</Alert>}{notice && <Alert color="teal" title="Work updated">{notice}</Alert>}
    <Box className="tailoring-board-v2">{boardStages.map((stage) => <Paper key={stage} withBorder p="md" className="tailoring-column-v2"><Group justify="space-between" mb="md"><Text fw={900}>{stageLabels[stage]}</Text><Badge variant="light" color={stage === 'READY' ? 'teal' : 'gray'}>{tasks.filter((task) => task.stage === stage).length}</Badge></Group><Stack gap="sm">{tasks.filter((task) => task.stage === stage).map((task) => <Card key={task.id} withBorder padding="sm"><Group gap="sm"><ThemeIcon variant="light" color={stage === 'READY' ? 'teal' : 'grape'}><Scissors size={16} /></ThemeIcon><Box><Text fw={800} size="sm">{task.item_name}</Text><Text size="xs" c="dimmed">{task.customer_name} · Order #{task.order_id}</Text></Box></Group><Group mt="sm" justify="space-between"><Badge size="xs" color={task.priority === 'URGENT' ? 'red' : 'gray'}>{task.priority}</Badge>{stage !== 'READY' && <Select size="xs" w={170} placeholder={stage === 'QC' ? 'QC result...' : 'Move to...'} value={null} onChange={(value) => value && void move(task, value as TailoringStage)} data={(nextStages[stage] ?? []).map((value) => ({ value, label: value === 'READY' ? 'Pass QC → Ready' : value === 'ALTERATION' ? 'Needs rework' : stageLabels[value] }))} />}{stage === 'READY' && task.order_status === 'READY' && <Button size="xs" color="teal" leftSection={<Check size={14} />} onClick={() => void deliver(task)}>Picked up</Button>}{stage === 'READY' && task.order_status !== 'READY' && <Badge size="xs" color="teal" variant="light">Garment ready</Badge>}</Group></Card>)}</Stack></Paper>)}</Box>
  </Stack>
}