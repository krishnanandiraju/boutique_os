import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Modal,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Check, Package, Plus, Scissors, Search, UserPlus, Users } from 'lucide-react'
import { api } from '../../api'
import type { Customer, Item, TailoringStage, TailoringTask } from '../../types'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

export function ProductsWorkspace() {
  const [items, setItems] = useState<Item[]>([])
  const [query, setQuery] = useState('')
  const [opened, { open, close }] = useDisclosure(false)
  const [form, setForm] = useState({ name: '', inventory_type: 'UNIQUE' as 'UNIQUE' | 'STOCKED' | 'YARDAGE', category: '', selling_price: '', quantity: '1' })
  const [error, setError] = useState('')

  function load() { void api.items().then(setItems).catch(() => setError('Unable to load products.')) }
  useEffect(load, [])

  const filtered = useMemo(() => items.filter((item) => `${item.name} ${item.category} ${item.fabric ?? ''} ${item.color ?? ''}`.toLowerCase().includes(query.toLowerCase())), [items, query])

  async function createProduct() {
    setError('')
    try {
      await api.addItem({ ...form, quantity: form.inventory_type === 'UNIQUE' ? '1' : form.quantity })
      setForm({ name: '', inventory_type: 'UNIQUE', category: '', selling_price: '', quantity: '1' })
      close(); load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create product.') }
  }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end"><Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Products</Title><Text c="dimmed" mt={4}>Inventory that understands unique pieces, stocked items and fabric.</Text></Box><Button color="grape" leftSection={<Plus size={16} />} onClick={open}>Add product</Button></Group>
    {error && <Alert color="red">{error}</Alert>}
    <TextInput size="md" leftSection={<Search size={17} />} placeholder="Search products, fabric, colour..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
      {filtered.map((item) => <Card key={item.id} withBorder padding="lg" className="product-card-v2"><Group justify="space-between" align="flex-start"><ThemeIcon size={44} variant="light" color="grape"><Package size={20} /></ThemeIcon><Badge color={item.availability === 'AVAILABLE' ? 'teal' : item.availability === 'HELD' ? 'orange' : 'gray'} variant="light">{item.availability.replaceAll('_', ' ')}</Badge></Group><Title order={3} mt="md">{item.name}</Title><Text size="sm" c="dimmed">{item.category}{item.fabric ? ` · ${item.fabric}` : ''}{item.color ? ` · ${item.color}` : ''}</Text><Group justify="space-between" mt="lg"><Box><Text size="xs" c="dimmed">{item.inventory_type}</Text><Text fw={800}>{item.inventory_type === 'YARDAGE' ? `${Number(item.quantity_available)} m` : `${Number(item.quantity_available)} available`}</Text></Box><Text fw={900} size="lg">{money(item.selling_price)}</Text></Group></Card>)}
    </SimpleGrid>
    <Modal opened={opened} onClose={close} title="Add product" centered><Stack><TextInput label="Product name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} /><Select label="Inventory type" data={[{value:'UNIQUE',label:'Unique piece'},{value:'STOCKED',label:'Stocked item'},{value:'YARDAGE',label:'Fabric / yardage'}]} value={form.inventory_type} onChange={(value) => value && setForm({ ...form, inventory_type: value as typeof form.inventory_type })} /><TextInput label="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.currentTarget.value })} /><TextInput label="Selling price" type="number" value={form.selling_price} onChange={(e) => setForm({ ...form, selling_price: e.currentTarget.value })} />{form.inventory_type !== 'UNIQUE' && <TextInput label={form.inventory_type === 'YARDAGE' ? 'Metres' : 'Quantity'} type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.currentTarget.value })} />}<Button color="grape" onClick={createProduct} disabled={!form.name || !form.category || !form.selling_price}>Create product</Button></Stack></Modal>
  </Stack>
}

export function CustomersWorkspace({ customers, onCreated }: { customers: Customer[]; onCreated: (customer: Customer) => void }) {
  const [query, setQuery] = useState('')
  const [opened, { open, close }] = useDisclosure(false)
  const [form, setForm] = useState({ name: '', phone: '', email: '' })
  const [error, setError] = useState('')
  const filtered = useMemo(() => customers.filter((customer) => `${customer.name} ${customer.phone} ${customer.email ?? ''}`.toLowerCase().includes(query.toLowerCase())), [customers, query])

  async function createCustomer() {
    setError('')
    try {
      const customer = await api.addCustomer(form)
      onCreated(customer); setForm({ name: '', phone: '', email: '' }); close()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create customer.') }
  }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end"><Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Customers</Title><Text c="dimmed" mt={4}>Customer profiles, measurements and order context in one place.</Text></Box><Button color="grape" leftSection={<UserPlus size={16} />} onClick={open}>New customer</Button></Group>
    {error && <Alert color="red">{error}</Alert>}
    <TextInput size="md" leftSection={<Search size={17} />} placeholder="Search name, phone or email..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>{filtered.map((customer) => <Card key={customer.id} withBorder padding="lg" className="customer-card-v2"><Group><ThemeIcon size={44} radius="xl" variant="light" color="grape"><Users size={20} /></ThemeIcon><Box><Text fw={900}>{customer.name}</Text><Text size="sm" c="dimmed">{customer.phone}</Text></Box></Group>{customer.email && <Text size="sm" mt="md">{customer.email}</Text>}<Group mt="lg"><Badge variant="light" color="grape">Measurements</Badge><Badge variant="light" color="gray">Order history</Badge></Group></Card>)}</SimpleGrid>
    <Modal opened={opened} onClose={close} title="New customer" centered><Stack><TextInput label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} /><TextInput label="Mobile" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.currentTarget.value })} /><TextInput label="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.currentTarget.value })} /><Button color="grape" onClick={createCustomer} disabled={!form.name || !form.phone}>Save customer</Button></Stack></Modal>
  </Stack>
}

const stageLabels: Record<TailoringStage, string> = {
  MEASUREMENT_PENDING: 'Measurements', CUTTING: 'Cutting', STITCHING: 'Stitching', QC: 'Quality check', TRIAL_SCHEDULED: 'Trial', ALTERATION: 'Alteration', READY: 'Ready',
}

export function TailoringWorkspace() {
  const [tasks, setTasks] = useState<TailoringTask[]>([])
  const [error, setError] = useState('')
  function load() { void api.tailoringTasks().then(setTasks).catch(() => setError('Unable to load tailoring work.')) }
  useEffect(load, [])

  async function move(task: TailoringTask, stage: TailoringStage) {
    try { await api.updateTailoringTask(task.id, { stage }); load() } catch (err) { setError(err instanceof Error ? err.message : 'Unable to update tailoring task.') }
  }

  const columns: TailoringStage[] = ['MEASUREMENT_PENDING', 'CUTTING', 'STITCHING', 'QC', 'READY']
  return <Stack gap="lg">
    <Box><Text size="sm" c="dimmed">Operations</Text><Title order={1}>Tailoring</Title><Text c="dimmed" mt={4}>Move work from measurements to ready without losing the customer context.</Text></Box>
    {error && <Alert color="red">{error}</Alert>}
    <Box className="tailoring-board-v2">{columns.map((stage) => <Paper key={stage} withBorder p="md" className="tailoring-column-v2"><Group justify="space-between" mb="md"><Text fw={900}>{stageLabels[stage]}</Text><Badge variant="light" color="gray">{tasks.filter((task) => task.stage === stage).length}</Badge></Group><Stack gap="sm">{tasks.filter((task) => task.stage === stage).map((task) => <Card key={task.id} withBorder padding="sm"><Group gap="sm"><ThemeIcon variant="light" color="grape"><Scissors size={16} /></ThemeIcon><Box><Text fw={800} size="sm">{task.item_name}</Text><Text size="xs" c="dimmed">{task.customer_name} · Order #{task.order_id}</Text></Box></Group><Group mt="sm" justify="space-between"><Badge size="xs" color={task.priority === 'URGENT' ? 'red' : 'gray'}>{task.priority}</Badge>{stage !== 'READY' && <Select size="xs" w={150} placeholder="Move to..." value={null} onChange={(value) => value && move(task, value as TailoringStage)} data={columns.filter((value) => value !== stage).map((value) => ({ value, label: stageLabels[value] }))} />}{stage === 'READY' && <ThemeIcon color="teal" variant="light"><Check size={15}/></ThemeIcon>}</Group></Card>)}</Stack></Paper>)}</Box>
  </Stack>
}
