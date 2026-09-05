import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  AppShell,
  Badge,
  Box,
  Burger,
  Button,
  Card,
  Divider,
  Group,
  NavLink,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  BarChart3,
  ClipboardRuler,
  LayoutDashboard,
  PackageCheck,
  Settings,
  ShoppingBag,
  Store,
  Users,
} from 'lucide-react'
import App from '../../App'
import { api } from '../../api'
import type { Customer, DashboardData, MeasurementProfile, MeasurementProfileDetail, Order } from '../../types'
import { IntegrationsPanel } from '../integrations/IntegrationsPanel'
import './boutique-workspace.css'

type PrimaryArea = 'Operations' | 'Reporting' | 'Admin'
type OperationsView = 'Dashboard' | 'Workbench' | 'Measurements'
type GarmentPreset = 'BLOUSE' | 'KURTA' | 'BOTTOM' | 'GENERAL'

const measurementPresets: Record<GarmentPreset, string[]> = {
  BLOUSE: ['bust', 'waist', 'shoulder', 'blouse_length', 'sleeve_length', 'armhole', 'front_neck_depth', 'back_neck_depth'],
  KURTA: ['bust', 'waist', 'hip', 'shoulder', 'kurta_length', 'sleeve_length', 'armhole'],
  BOTTOM: ['waist', 'hip', 'length', 'thigh', 'bottom_opening'],
  GENERAL: [],
}

const fieldLabels: Record<string, string> = {
  bust: 'Bust',
  waist: 'Waist',
  hip: 'Hip',
  shoulder: 'Shoulder',
  blouse_length: 'Blouse length',
  kurta_length: 'Kurta length',
  sleeve_length: 'Sleeve length',
  armhole: 'Armhole',
  front_neck_depth: 'Front neck depth',
  back_neck_depth: 'Back neck depth',
  length: 'Length',
  thigh: 'Thigh',
  bottom_opening: 'Bottom opening',
}

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function Dashboard({ dashboard, onMeasurements, onWorkbench }: {
  dashboard: DashboardData | null
  onMeasurements: () => void
  onWorkbench: () => void
}) {
  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Text size="sm" c="dimmed">Meera Boutique</Text>
          <Title order={1}>Today</Title>
        </Box>
        <Group>
          <Button variant="light" color="grape" leftSection={<ClipboardRuler size={17} />} onClick={onMeasurements}>Take measurements</Button>
          <Button color="grape" leftSection={<ShoppingBag size={17} />} onClick={onWorkbench}>Open workbench</Button>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
        <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card>
        <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Pending orders</Text><Title order={3} mt={6}>{dashboard?.orders_pending ?? '—'}</Title></Card>
        <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Tailoring due</Text><Title order={3} mt={6}>{dashboard?.tailoring_pending ?? '—'}</Title></Card>
        <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Held pieces</Text><Title order={3} mt={6}>{dashboard?.held_items ?? '—'}</Title></Card>
      </SimpleGrid>

      <Paper withBorder p="lg">
        <Group justify="space-between" mb="md"><Title order={3}>Needs attention</Title><Badge variant="light" color="orange">Live operations</Badge></Group>
        <Stack gap="sm">
          <Group justify="space-between"><Text>Tailoring work in progress</Text><Text fw={700}>{dashboard?.tailoring_pending ?? '—'}</Text></Group>
          <Divider />
          <Group justify="space-between"><Text>Unique pieces currently held</Text><Text fw={700}>{dashboard?.held_items ?? '—'}</Text></Group>
          <Divider />
          <Group justify="space-between"><Text>Low-stock items</Text><Text fw={700}>{dashboard?.low_stock_items ?? '—'}</Text></Group>
          <Divider />
          <Group justify="space-between"><Text>Fabric remnants</Text><Text fw={700}>{dashboard?.remnant_rolls ?? '—'}</Text></Group>
        </Stack>
      </Paper>
    </Stack>
  )
}

function MeasurementsWorkspace({ customers }: { customers: Customer[] }) {
  const [customerId, setCustomerId] = useState<number | null>(customers[0]?.id ?? null)
  const [profiles, setProfiles] = useState<MeasurementProfile[]>([])
  const [profile, setProfile] = useState<MeasurementProfileDetail | null>(null)
  const [profileName, setProfileName] = useState('Self')
  const [garment, setGarment] = useState<GarmentPreset>('BLOUSE')
  const [unit, setUnit] = useState<'INCH' | 'CM'>('INCH')
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!customerId && customers[0]) setCustomerId(customers[0].id)
  }, [customers, customerId])

  useEffect(() => {
    if (!customerId) return
    setError('')
    void api.customerMeasurementProfiles(customerId)
      .then(async (result) => {
        setProfiles(result)
        if (result[0]) {
          const detail = await api.measurementProfile(result[0].id)
          setProfile(detail)
          setProfileName(detail.name)
          setGarment((detail.garment_type as GarmentPreset) || 'GENERAL')
          setUnit(detail.unit)
          const latest = detail.latest_version
          setValues(latest ? Object.fromEntries(Object.entries(latest.measurements).map(([key, value]) => [key, String(value)])) : {})
          setNotes(latest?.notes || '')
        } else {
          setProfile(null)
          setProfileName('Self')
          setGarment('BLOUSE')
          setUnit('INCH')
          setValues({})
          setNotes('')
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load measurements'))
  }, [customerId])

  const fields = useMemo(() => measurementPresets[garment], [garment])

  async function chooseProfile(profileId: string | null) {
    if (!profileId) {
      setProfile(null)
      setProfileName('Self')
      setGarment('BLOUSE')
      setUnit('INCH')
      setValues({})
      setNotes('')
      return
    }
    try {
      const detail = await api.measurementProfile(Number(profileId))
      setProfile(detail)
      setProfileName(detail.name)
      setGarment((detail.garment_type as GarmentPreset) || 'GENERAL')
      setUnit(detail.unit)
      const latest = detail.latest_version
      setValues(latest ? Object.fromEntries(Object.entries(latest.measurements).map(([key, value]) => [key, String(value)])) : {})
      setNotes(latest?.notes || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load profile')
    }
  }

  async function saveMeasurements() {
    if (!customerId) return
    const measurementPayload = Object.fromEntries(
      Object.entries(values).filter(([, value]) => value.trim() !== '').map(([key, value]) => [key, value]),
    )
    if (Object.keys(measurementPayload).length === 0) {
      setError('Enter at least one measurement before saving.')
      return
    }

    setSaving(true)
    setError('')
    setMessage('')
    try {
      if (profile) {
        await api.createMeasurementVersion(profile.id, { measurements: measurementPayload, notes: notes || undefined })
        const updated = await api.measurementProfile(profile.id)
        setProfile(updated)
        setMessage(`Saved measurement version ${updated.latest_version?.version_number ?? ''}`)
      } else {
        const created = await api.createMeasurementProfile(customerId, {
          name: profileName,
          garment_type: garment,
          unit,
          measurements: measurementPayload,
          notes: notes || undefined,
        })
        setProfile(created)
        setProfiles(await api.customerMeasurementProfiles(customerId))
        setMessage('Measurement profile created')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save measurements')
    } finally {
      setSaving(false)
    }
  }

  const selectedCustomer = customers.find((customer) => customer.id === customerId)

  return (
    <Stack gap="lg">
      <Box>
        <Text size="sm" c="dimmed">Operations</Text>
        <Title order={1}>Measurements</Title>
        <Text c="dimmed" mt={6}>Record the measurements used for the customer’s next garment. Previous versions remain unchanged.</Text>
      </Box>

      {error && <Alert color="red" title="Unable to continue">{error}</Alert>}
      {message && <Alert color="teal" title="Saved">{message}</Alert>}

      <Paper withBorder p="lg">
        <SimpleGrid cols={{ base: 1, md: 4 }} spacing="md">
          <Select label="Customer" searchable value={customerId?.toString() ?? null} onChange={(value) => setCustomerId(value ? Number(value) : null)} data={customers.map((customer) => ({ value: String(customer.id), label: `${customer.name} · ${customer.phone}` }))} />
          <Select label="Profile" value={profile?.id.toString() ?? 'new'} onChange={(value) => chooseProfile(value === 'new' ? null : value)} data={[{ value: 'new', label: '+ New profile' }, ...profiles.map((item) => ({ value: String(item.id), label: item.name }))]} />
          <Select label="Garment" value={garment} disabled={Boolean(profile)} onChange={(value) => setGarment((value as GarmentPreset) || 'BLOUSE')} data={[{ value: 'BLOUSE', label: 'Blouse' }, { value: 'KURTA', label: 'Kurta' }, { value: 'BOTTOM', label: 'Bottom' }, { value: 'GENERAL', label: 'General' }]} />
          <Select label="Unit" value={unit} disabled={Boolean(profile)} onChange={(value) => setUnit((value as 'INCH' | 'CM') || 'INCH')} data={[{ value: 'INCH', label: 'Inches' }, { value: 'CM', label: 'Centimetres' }]} />
        </SimpleGrid>
        {!profile && <TextInput label="Profile name" value={profileName} onChange={(event) => setProfileName(event.currentTarget.value)} mt="md" maw={320} />}
      </Paper>

      <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="lg">
        <Paper withBorder p="lg" className="measurement-form-card" style={{ gridColumn: 'span 2' }}>
          <Group justify="space-between" mb="lg">
            <Box><Text size="xs" fw={700} c="grape.6" tt="uppercase">{garment.replace('_', ' ')}</Text><Title order={3}>{selectedCustomer?.name || 'Customer'} measurements</Title></Box>
            {profile?.latest_version && <Badge variant="light" color="grape">Version {profile.latest_version.version_number}</Badge>}
          </Group>

          {fields.length > 0 ? (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              {fields.map((field) => (
                <TextInput key={field} label={fieldLabels[field] || field} rightSection={<Text size="xs" c="dimmed">{unit === 'INCH' ? 'in' : 'cm'}</Text>} value={values[field] || ''} onChange={(event) => setValues((current) => ({ ...current, [field]: event.currentTarget.value }))} inputMode="decimal" placeholder="0.0" />
              ))}
            </SimpleGrid>
          ) : (
            <Alert color="gray">General profiles can be saved through the existing customer workflow. Choose a garment preset here for guided measurement entry.</Alert>
          )}
          <TextInput label="Notes" value={notes} onChange={(event) => setNotes(event.currentTarget.value)} mt="lg" placeholder="Fit, posture or tailoring notes" />
          <Group justify="flex-end" mt="lg"><Button color="grape" loading={saving} onClick={saveMeasurements}>{profile ? 'Save new version' : 'Create measurement profile'}</Button></Group>
        </Paper>

        <Paper withBorder p="lg">
          <Title order={4}>History</Title>
          <Text size="sm" c="dimmed" mt={4}>Measurements are versioned; past orders keep the version originally used.</Text>
          <Stack gap="sm" mt="lg">
            {profile?.versions?.length ? profile.versions.slice().reverse().map((version) => (
              <Card key={version.id} withBorder padding="sm">
                <Group justify="space-between"><Text fw={700}>Version {version.version_number}</Text><Text size="xs" c="dimmed">{new Date(version.created_at).toLocaleDateString()}</Text></Group>
                <Text size="xs" c="dimmed" mt={4}>{Object.keys(version.measurements).length} measurements recorded</Text>
              </Card>
            )) : <Text size="sm" c="dimmed">No saved measurement history yet.</Text>}
          </Stack>
        </Paper>
      </SimpleGrid>
    </Stack>
  )
}

function Reporting({ dashboard, orders }: { dashboard: DashboardData | null; orders: Order[] }) {
  const delivered = orders.filter((order) => order.status === 'DELIVERED').length
  const active = orders.filter((order) => !['DELIVERED', 'CANCELLED'].includes(order.status)).length
  return (
    <Stack gap="lg">
      <Box><Text size="sm" c="dimmed">Reporting</Text><Title order={1}>Business snapshot</Title></Box>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card>
        <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Active orders</Text><Title order={3} mt={6}>{active}</Title></Card>
        <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Delivered</Text><Title order={3} mt={6}>{delivered}</Title></Card>
        <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Available items</Text><Title order={3} mt={6}>{dashboard?.available_items ?? '—'}</Title></Card>
      </SimpleGrid>
      <Paper withBorder p="lg">
        <Title order={3}>Operational indicators</Title>
        <SimpleGrid cols={{ base: 1, md: 3 }} mt="md">
          <Card withBorder><Text c="dimmed" size="sm">Pending orders</Text><Text size="xl" fw={800}>{dashboard?.orders_pending ?? '—'}</Text></Card>
          <Card withBorder><Text c="dimmed" size="sm">Tailoring in progress</Text><Text size="xl" fw={800}>{dashboard?.tailoring_pending ?? '—'}</Text></Card>
          <Card withBorder><Text c="dimmed" size="sm">Low stock</Text><Text size="xl" fw={800}>{dashboard?.low_stock_items ?? '—'}</Text></Card>
        </SimpleGrid>
      </Paper>
    </Stack>
  )
}

export default function BoutiqueWorkspace() {
  const [area, setArea] = useState<PrimaryArea>('Operations')
  const [operationsView, setOperationsView] = useState<OperationsView>('Dashboard')
  const [opened, { toggle, close }] = useDisclosure(false)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    void Promise.all([api.dashboard(), api.customers(), api.orders()])
      .then(([dashboardResult, customerResult, orderResult]) => {
        setDashboard(dashboardResult)
        setCustomers(customerResult)
        setOrders(orderResult)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load BoutiqueOS'))
  }, [])

  function go(next: PrimaryArea) {
    setArea(next)
    close()
  }

  return (
    <AppShell header={{ height: 68 }} navbar={{ width: 248, breakpoint: 'md', collapsed: { mobile: !opened } }} padding="md" className="boutique-workspace">
      <AppShell.Header className="boutique-header">
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label="Open navigation" />
            <ThemeIcon size={40} radius="md" color="grape"><Store size={21} /></ThemeIcon>
            <Box><Text fw={800} size="lg">BoutiqueOS</Text><Text size="xs" c="dimmed">Meera Boutique</Text></Box>
          </Group>
          <Badge variant="dot" color="teal" visibleFrom="sm">Online</Badge>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" className="boutique-navbar">
        <Stack h="100%" gap="xs">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>Workspace</Text>
          <NavLink active={area === 'Operations'} label="Operations" description="Daily boutique work" leftSection={<ShoppingBag size={18} />} onClick={() => go('Operations')} color="grape" variant="light" />
          <NavLink active={area === 'Reporting'} label="Reporting" description="Business performance" leftSection={<BarChart3 size={18} />} onClick={() => go('Reporting')} color="grape" variant="light" />
          <NavLink active={area === 'Admin'} label="Admin" description="Settings & connections" leftSection={<Settings size={18} />} onClick={() => go('Admin')} color="grape" variant="light" />
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <Box className="boutique-page">
          {error && <Alert color="red" mb="md" title="Unable to load operations">We couldn't connect to BoutiqueOS. Please try again.</Alert>}

          {area === 'Operations' && (
            <Stack gap="md">
              <Tabs value={operationsView} onChange={(value) => setOperationsView((value as OperationsView) || 'Dashboard')} color="grape" variant="pills">
                <Tabs.List>
                  <Tabs.Tab value="Dashboard" leftSection={<LayoutDashboard size={15} />}>Dashboard</Tabs.Tab>
                  <Tabs.Tab value="Workbench" leftSection={<PackageCheck size={15} />}>Products, customers & orders</Tabs.Tab>
                  <Tabs.Tab value="Measurements" leftSection={<ClipboardRuler size={15} />}>Measurements</Tabs.Tab>
                </Tabs.List>
              </Tabs>

              {operationsView === 'Dashboard' && <Dashboard dashboard={dashboard} onMeasurements={() => setOperationsView('Measurements')} onWorkbench={() => setOperationsView('Workbench')} />}
              {operationsView === 'Workbench' && <Box className="embedded-workbench"><App /></Box>}
              {operationsView === 'Measurements' && <MeasurementsWorkspace customers={customers} />}
            </Stack>
          )}

          {area === 'Reporting' && <Reporting dashboard={dashboard} orders={orders} />}

          {area === 'Admin' && (
            <Stack gap="lg">
              <Box><Text size="sm" c="dimmed">Admin</Text><Title order={1}>Settings & connections</Title></Box>
              <SimpleGrid cols={{ base: 1, md: 2 }}>
                <Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Store size={18} /></ThemeIcon><Box><Text fw={700}>Boutique</Text><Text size="sm" c="dimmed">Meera Boutique</Text></Box></Group></Card>
                <Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Users size={18} /></ThemeIcon><Box><Text fw={700}>Staff & access</Text><Text size="sm" c="dimmed">User administration will live here.</Text></Box></Group></Card>
              </SimpleGrid>
              <IntegrationsPanel />
            </Stack>
          )}
        </Box>
      </AppShell.Main>
    </AppShell>
  )
}
