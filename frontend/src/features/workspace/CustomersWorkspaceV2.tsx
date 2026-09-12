import { useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Box, Button, Group, Modal, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { CalendarHeart, Search, UserPlus } from 'lucide-react'
import { api } from '../../api'
import { customerCrmApi, type CustomerProfileSummary } from '../../customerCrmApi'
import type { Customer, Order } from '../../types'
import { CustomerCrmModal } from './CustomerCrmModal'
import './final-ux.css'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

export function CustomersWorkspaceV2({ customers, onCreated }: { customers: Customer[]; onCreated: (customer: Customer) => void }) {
  const [query, setQuery] = useState('')
  const [orders, setOrders] = useState<Order[]>([])
  const [profileCounts, setProfileCounts] = useState<Record<number, number>>({})
  const [crmSummaries, setCrmSummaries] = useState<Record<number, CustomerProfileSummary>>({})
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)
  const [crmOpened, setCrmOpened] = useState(false)
  const [opened, setOpened] = useState(false)
  const [form, setForm] = useState({ name: '', phone: '', email: '' })
  const [error, setError] = useState('')

  function loadCrm() {
    void customerCrmApi.summaries()
      .then((rows) => setCrmSummaries(Object.fromEntries(rows.map((row) => [row.customer_id, row]))))
      .catch(() => undefined)
  }

  useEffect(() => { void api.orders().then(setOrders).catch(() => undefined); loadCrm() }, [])
  useEffect(() => {
    let active = true
    void Promise.all(customers.map(async (customer) => [customer.id, (await api.customerMeasurementProfiles(customer.id)).length] as const))
      .then((pairs) => { if (active) setProfileCounts(Object.fromEntries(pairs)) })
      .catch(() => undefined)
    loadCrm()
    return () => { active = false }
  }, [customers])

  const filtered = useMemo(() => customers.filter((customer) => {
    const crm = crmSummaries[customer.id]
    const searchable = `${customer.name} ${customer.phone} ${customer.email ?? ''} ${crm?.merchant_tags.join(' ') ?? ''} ${crm?.customer_segment ?? ''} ${crm?.city ?? ''} ${crm?.acquisition_source ?? ''}`
    return searchable.toLowerCase().includes(query.toLowerCase())
  }), [customers, query, crmSummaries])

  async function createCustomer() {
    setError('')
    try {
      const customer = await api.addCustomer(form)
      onCreated(customer)
      setForm({ name: '', phone: '', email: '' })
      setOpened(false)
      setSelectedCustomer(customer)
      setCrmOpened(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to create customer.') }
  }

  function customerOrders(customerId: number) { return orders.filter((order) => order.customer_id === customerId) }
  function openCrm(customer: Customer) { setSelectedCustomer(customer); setCrmOpened(true) }

  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end">
      <Box><Text size="sm" c="dimmed">Customer operations</Text><Title order={1}>Customers</Title><Text c="dimmed" mt={4}>Customer memory, purchase value, preferences and upcoming moments in one place.</Text></Box>
      <Button color="grape" leftSection={<UserPlus size={16} />} onClick={() => setOpened(true)}>New customer</Button>
    </Group>
    {error && <Alert color="red">{error}</Alert>}
    <TextInput size="md" leftSection={<Search size={17} />} placeholder="Search name, phone, tag, segment, city or source..." value={query} onChange={(event) => setQuery(event.currentTarget.value)} />
    <Box className="customer-table-card">
      <Table.ScrollContainer minWidth={1180}>
        <Table verticalSpacing="sm" highlightOnHover>
          <Table.Thead><Table.Tr><Table.Th>Customer</Table.Th><Table.Th>CRM context</Table.Th><Table.Th>Measurements</Table.Th><Table.Th>Orders</Table.Th><Table.Th>Lifetime spend</Table.Th><Table.Th>AOV</Table.Th><Table.Th>Next moment</Table.Th><Table.Th></Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>{filtered.map((customer) => {
            const rows = customerOrders(customer.id)
            const crm = crmSummaries[customer.id]
            return <Table.Tr key={customer.id}>
              <Table.Td><Stack gap={1}><Text className="customer-row-name">{customer.name}</Text><Text size="xs" c="dimmed">{customer.phone}{customer.email ? ` · ${customer.email}` : ''}</Text></Stack></Table.Td>
              <Table.Td><Stack gap={4}><Group gap={4}>{crm?.customer_segment && <Badge size="xs" color="grape" variant="light">{crm.customer_segment}</Badge>}{crm?.merchant_tags.slice(0, 2).map((tag) => <Badge key={tag} size="xs" variant="outline">{tag}</Badge>)}</Group><Text size="xs" c="dimmed">{[crm?.city, crm?.acquisition_source].filter(Boolean).join(' · ') || 'Profile not enriched yet'}</Text></Stack></Table.Td>
              <Table.Td><Badge variant="light" color={profileCounts[customer.id] ? 'grape' : 'gray'}>{profileCounts[customer.id] ?? 0}</Badge></Table.Td>
              <Table.Td>{crm?.order_count ?? rows.length}</Table.Td>
              <Table.Td><Text fw={700}>{money(crm?.total_spend ?? 0)}</Text></Table.Td>
              <Table.Td>{money(crm?.average_order_value ?? 0)}</Table.Td>
              <Table.Td>{crm?.next_event_date ? <Stack gap={1}><Group gap={5}><CalendarHeart size={14}/><Text size="sm" fw={700}>{crm.next_event_label}</Text></Group><Text size="xs" c="dimmed">{new Date(`${crm.next_event_date}T00:00:00`).toLocaleDateString('en-IN')}</Text></Stack> : <Text size="sm" c="dimmed">—</Text>}</Table.Td>
              <Table.Td><Button size="xs" variant="light" color="grape" onClick={() => openCrm(customer)}>CRM profile</Button></Table.Td>
            </Table.Tr>
          })}</Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Box>

    <Modal opened={opened} onClose={() => setOpened(false)} title="New customer" centered>
      <Stack><TextInput label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} /><TextInput label="Mobile" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.currentTarget.value })} /><TextInput label="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.currentTarget.value })} /><Button color="grape" onClick={() => void createCustomer()} disabled={!form.name || !form.phone}>Save & enrich customer</Button></Stack>
    </Modal>
    <CustomerCrmModal customer={selectedCustomer} opened={crmOpened} onClose={() => setCrmOpened(false)} onSaved={loadCrm} />
  </Stack>
}
