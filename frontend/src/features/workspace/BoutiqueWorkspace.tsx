import { useEffect, useState } from 'react'
import { Alert, AppShell, Badge, Box, Burger, Button, Card, Divider, Group, NavLink, Paper, SimpleGrid, Stack, Tabs, Text, ThemeIcon, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { BarChart3, LayoutDashboard, PackageCheck, Ruler, Settings, ShoppingBag, Store, Users } from 'lucide-react'
import App from '../../App'
import { api } from '../../api'
import type { Customer, DashboardData, Order } from '../../types'
import { IntegrationsPanel } from '../integrations/IntegrationsPanel'
import { VisualMeasurementsWorkspace } from './VisualMeasurementsWorkspace'
import './boutique-workspace.css'

type PrimaryArea = 'Operations' | 'Reporting' | 'Admin'
type OperationsView = 'Dashboard' | 'Workbench' | 'Measurements'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function Dashboard({ dashboard, onMeasurements, onWorkbench }: { dashboard: DashboardData | null; onMeasurements: () => void; onWorkbench: () => void }) {
  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end">
      <Box><Text size="sm" c="dimmed">Meera Boutique</Text><Title order={1}>Today</Title></Box>
      <Group><Button variant="light" color="grape" leftSection={<Ruler size={17} />} onClick={onMeasurements}>Take measurements</Button><Button color="grape" leftSection={<ShoppingBag size={17} />} onClick={onWorkbench}>Open workbench</Button></Group>
    </Group>
    <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
      <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card>
      <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Pending orders</Text><Title order={3} mt={6}>{dashboard?.orders_pending ?? '—'}</Title></Card>
      <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Tailoring due</Text><Title order={3} mt={6}>{dashboard?.tailoring_pending ?? '—'}</Title></Card>
      <Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Held pieces</Text><Title order={3} mt={6}>{dashboard?.held_items ?? '—'}</Title></Card>
    </SimpleGrid>
    <Paper withBorder p="lg">
      <Group justify="space-between" mb="md"><Title order={3}>Needs attention</Title><Badge variant="light" color="orange">Live operations</Badge></Group>
      <Stack gap="sm"><Group justify="space-between"><Text>Tailoring work in progress</Text><Text fw={700}>{dashboard?.tailoring_pending ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Unique pieces currently held</Text><Text fw={700}>{dashboard?.held_items ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Low-stock items</Text><Text fw={700}>{dashboard?.low_stock_items ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Fabric remnants</Text><Text fw={700}>{dashboard?.remnant_rolls ?? '—'}</Text></Group></Stack>
    </Paper>
  </Stack>
}

function Reporting({ dashboard, orders }: { dashboard: DashboardData | null; orders: Order[] }) {
  const delivered = orders.filter((order) => order.status === 'DELIVERED').length
  const active = orders.filter((order) => !['DELIVERED', 'CANCELLED'].includes(order.status)).length
  return <Stack gap="lg">
    <Box><Text size="sm" c="dimmed">Reporting</Text><Title order={1}>Business snapshot</Title></Box>
    <SimpleGrid cols={{ base: 2, md: 4 }}>
      <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card>
      <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Active orders</Text><Title order={3} mt={6}>{active}</Title></Card>
      <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Delivered</Text><Title order={3} mt={6}>{delivered}</Title></Card>
      <Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Available items</Text><Title order={3} mt={6}>{dashboard?.available_items ?? '—'}</Title></Card>
    </SimpleGrid>
    <Paper withBorder p="lg"><Title order={3}>Operational indicators</Title><SimpleGrid cols={{ base: 1, md: 3 }} mt="md"><Card withBorder><Text c="dimmed" size="sm">Pending orders</Text><Text size="xl" fw={800}>{dashboard?.orders_pending ?? '—'}</Text></Card><Card withBorder><Text c="dimmed" size="sm">Tailoring in progress</Text><Text size="xl" fw={800}>{dashboard?.tailoring_pending ?? '—'}</Text></Card><Card withBorder><Text c="dimmed" size="sm">Low stock</Text><Text size="xl" fw={800}>{dashboard?.low_stock_items ?? '—'}</Text></Card></SimpleGrid></Paper>
  </Stack>
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
    void Promise.all([api.dashboard(), api.customers(), api.orders()]).then(([dashboardResult, customerResult, orderResult]) => { setDashboard(dashboardResult); setCustomers(customerResult); setOrders(orderResult) }).catch(() => setError('Unable to load BoutiqueOS'))
  }, [])

  function go(next: PrimaryArea) { setArea(next); close() }

  return <AppShell header={{ height: 68 }} navbar={{ width: 248, breakpoint: 'md', collapsed: { mobile: !opened } }} padding="md" className="boutique-workspace">
    <AppShell.Header className="boutique-header"><Group h="100%" px="md" justify="space-between"><Group gap="sm"><Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label="Open navigation" /><ThemeIcon size={40} radius="md" color="grape"><Store size={21} /></ThemeIcon><Box><Text fw={800} size="lg">BoutiqueOS</Text><Text size="xs" c="dimmed">Meera Boutique</Text></Box></Group><Badge variant="dot" color="teal" visibleFrom="sm">Online</Badge></Group></AppShell.Header>
    <AppShell.Navbar p="md" className="boutique-navbar"><Stack h="100%" gap="xs"><Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={4}>Workspace</Text><NavLink active={area === 'Operations'} label="Operations" description="Daily boutique work" leftSection={<ShoppingBag size={18} />} onClick={() => go('Operations')} color="grape" variant="light" /><NavLink active={area === 'Reporting'} label="Reporting" description="Business performance" leftSection={<BarChart3 size={18} />} onClick={() => go('Reporting')} color="grape" variant="light" /><NavLink active={area === 'Admin'} label="Admin" description="Settings & connections" leftSection={<Settings size={18} />} onClick={() => go('Admin')} color="grape" variant="light" /></Stack></AppShell.Navbar>
    <AppShell.Main><Box className="boutique-page">
      {error && <Alert color="red" mb="md" title="Unable to load operations">We couldn't connect to BoutiqueOS. Please try again.</Alert>}
      {area === 'Operations' && <Stack gap="md">
        <Tabs value={operationsView} onChange={(value) => setOperationsView((value as OperationsView) || 'Dashboard')} color="grape" variant="pills"><Tabs.List><Tabs.Tab value="Dashboard" leftSection={<LayoutDashboard size={15} />}>Dashboard</Tabs.Tab><Tabs.Tab value="Workbench" leftSection={<PackageCheck size={15} />}>Products, customers & orders</Tabs.Tab><Tabs.Tab value="Measurements" leftSection={<Ruler size={15} />}>Measurements</Tabs.Tab></Tabs.List></Tabs>
        {operationsView === 'Dashboard' && <Dashboard dashboard={dashboard} onMeasurements={() => setOperationsView('Measurements')} onWorkbench={() => setOperationsView('Workbench')} />}
        {operationsView === 'Workbench' && <Box className="embedded-workbench"><App /></Box>}
        {operationsView === 'Measurements' && <VisualMeasurementsWorkspace customers={customers} />}
      </Stack>}
      {area === 'Reporting' && <Reporting dashboard={dashboard} orders={orders} />}
      {area === 'Admin' && <Stack gap="lg"><Box><Text size="sm" c="dimmed">Admin</Text><Title order={1}>Settings & connections</Title></Box><SimpleGrid cols={{ base: 1, md: 2 }}><Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Store size={18} /></ThemeIcon><Box><Text fw={700}>Boutique</Text><Text size="sm" c="dimmed">Meera Boutique</Text></Box></Group></Card><Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Users size={18} /></ThemeIcon><Box><Text fw={700}>Staff & access</Text><Text size="sm" c="dimmed">User administration will live here.</Text></Box></Group></Card></SimpleGrid><IntegrationsPanel /></Stack>}
    </Box></AppShell.Main>
  </AppShell>
}
