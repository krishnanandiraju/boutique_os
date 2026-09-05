import { useEffect, useState } from 'react'
import { Alert, AppShell, Badge, Box, Burger, Button, Card, Divider, Group, NavLink, Paper, SimpleGrid, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { BarChart3, LayoutDashboard, Package, Ruler, Scissors, Settings, ShoppingBag, Store, Users } from 'lucide-react'
import { api } from '../../api'
import type { Customer, DashboardData, Order } from '../../types'
import { IntegrationsPanel } from '../integrations/IntegrationsPanel'
import { CatalogWorkspaceV3 } from './CatalogWorkspaceV3'
import { GuidedOrdersWorkspaceV3 } from './GuidedOrdersWorkspaceV3'
import { TenantSettingsPanel } from './TenantSettingsPanel'
import { VisualMeasurementsWorkspaceV3 } from './VisualMeasurementsWorkspaceV3'
import { CustomersWorkspace, TailoringWorkspace } from './OperationsWorkspaces'
import './boutique-workspace.css'

type Area = 'Dashboard' | 'Products' | 'Customers' | 'Orders' | 'Measurements' | 'Tailoring' | 'Reporting' | 'Admin'

function money(value: string | number) {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function Dashboard({ dashboard, onNavigate }: { dashboard: DashboardData | null; onNavigate: (area: Area) => void }) {
  return <Stack gap="lg">
    <Group justify="space-between" align="flex-end" className="page-heading-v2"><Box><Text size="sm" c="dimmed">Meera Boutique</Text><Title order={1}>Today</Title><Text c="dimmed" mt={4}>What needs your attention right now.</Text></Box><Group><Button variant="light" color="grape" leftSection={<Ruler size={17} />} onClick={() => onNavigate('Measurements')}>Take measurements</Button><Button color="grape" leftSection={<ShoppingBag size={17} />} onClick={() => onNavigate('Orders')}>New order</Button></Group></Group>
    <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md"><Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card><Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Pending orders</Text><Title order={3} mt={6}>{dashboard?.orders_pending ?? '—'}</Title></Card><Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Tailoring due</Text><Title order={3} mt={6}>{dashboard?.tailoring_pending ?? '—'}</Title></Card><Card withBorder padding="lg"><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Held pieces</Text><Title order={3} mt={6}>{dashboard?.held_items ?? '—'}</Title></Card></SimpleGrid>
    <Paper withBorder p="lg"><Group justify="space-between" mb="md"><Title order={3}>Needs attention</Title><Badge variant="light" color="grape">Live</Badge></Group><Stack gap="sm"><Group justify="space-between"><Text>Tailoring work in progress</Text><Text fw={700}>{dashboard?.tailoring_pending ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Unique pieces currently held</Text><Text fw={700}>{dashboard?.held_items ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Low-stock items</Text><Text fw={700}>{dashboard?.low_stock_items ?? '—'}</Text></Group><Divider /><Group justify="space-between"><Text>Fabric remnants</Text><Text fw={700}>{dashboard?.remnant_rolls ?? '—'}</Text></Group></Stack></Paper>
    <SimpleGrid cols={{ base: 2, md: 4 }}><Button variant="default" h={72} leftSection={<Package size={20}/>} onClick={() => onNavigate('Products')}>Products</Button><Button variant="default" h={72} leftSection={<Users size={20}/>} onClick={() => onNavigate('Customers')}>Customers</Button><Button variant="default" h={72} leftSection={<ShoppingBag size={20}/>} onClick={() => onNavigate('Orders')}>Orders</Button><Button variant="default" h={72} leftSection={<Scissors size={20}/>} onClick={() => onNavigate('Tailoring')}>Tailoring</Button></SimpleGrid>
  </Stack>
}

function Reporting({ dashboard, orders }: { dashboard: DashboardData | null; orders: Order[] }) {
  const delivered = orders.filter((order) => order.status === 'DELIVERED').length
  const active = orders.filter((order) => !['DELIVERED', 'CANCELLED'].includes(order.status)).length
  return <Stack gap="lg"><Box><Text size="sm" c="dimmed">Reporting</Text><Title order={1}>Business snapshot</Title></Box><SimpleGrid cols={{ base: 2, md: 4 }}><Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Sales today</Text><Title order={3} mt={6}>{dashboard ? money(dashboard.sales_today) : '—'}</Title></Card><Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Active orders</Text><Title order={3} mt={6}>{active}</Title></Card><Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Delivered</Text><Title order={3} mt={6}>{delivered}</Title></Card><Card withBorder><Text size="xs" c="dimmed" tt="uppercase" fw={700}>Available items</Text><Title order={3} mt={6}>{dashboard?.available_items ?? '—'}</Title></Card></SimpleGrid><Paper withBorder p="lg"><Title order={3}>Operational indicators</Title><SimpleGrid cols={{ base: 1, md: 3 }} mt="md"><Card withBorder><Text c="dimmed" size="sm">Pending orders</Text><Text size="xl" fw={800}>{dashboard?.orders_pending ?? '—'}</Text></Card><Card withBorder><Text c="dimmed" size="sm">Tailoring in progress</Text><Text size="xl" fw={800}>{dashboard?.tailoring_pending ?? '—'}</Text></Card><Card withBorder><Text c="dimmed" size="sm">Low stock</Text><Text size="xl" fw={800}>{dashboard?.low_stock_items ?? '—'}</Text></Card></SimpleGrid></Paper></Stack>
}

const nav: Array<{ area: Area; label: string; icon: typeof LayoutDashboard }> = [
  { area: 'Dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { area: 'Products', label: 'Products', icon: Package },
  { area: 'Customers', label: 'Customers', icon: Users },
  { area: 'Orders', label: 'Orders', icon: ShoppingBag },
  { area: 'Measurements', label: 'Measurements', icon: Ruler },
  { area: 'Tailoring', label: 'Tailoring', icon: Scissors },
]

export default function BoutiqueWorkspace() {
  const [area, setArea] = useState<Area>('Dashboard')
  const [opened, { toggle, close }] = useDisclosure(false)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [error, setError] = useState('')

  function refreshOperations() {
    void Promise.all([api.dashboard(), api.customers(), api.orders()]).then(([d, c, o]) => { setDashboard(d); setCustomers(c); setOrders(o) }).catch(() => setError('Unable to load BoutiqueOS'))
  }
  useEffect(refreshOperations, [])

  function go(next: Area) { setArea(next); close() }
  function handleCustomerCreated(customer: Customer) { setCustomers((current) => [customer, ...current]) }

  return <AppShell header={{ height: 68 }} navbar={{ width: 230, breakpoint: 'md', collapsed: { mobile: !opened } }} padding="md" className="boutique-workspace">
    <AppShell.Header className="boutique-header"><Group h="100%" px="md" justify="space-between"><Group gap="sm"><Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label="Open navigation" /><ThemeIcon size={40} radius="md" color="grape"><Store size={21} /></ThemeIcon><Box><Text fw={900} size="lg">BoutiqueOS</Text><Text size="xs" c="dimmed">Meera Boutique</Text></Box></Group><Badge variant="dot" color="teal" visibleFrom="sm">Online</Badge></Group></AppShell.Header>
    <AppShell.Navbar p="md" className="boutique-navbar"><Stack h="100%" gap={4}>{nav.map((item) => { const Icon = item.icon; return <NavLink key={item.area} active={area === item.area} label={item.label} leftSection={<Icon size={18} />} onClick={() => go(item.area)} color="grape" variant="light" /> })}<Divider my="sm"/><NavLink active={area === 'Reporting'} label="Reporting" leftSection={<BarChart3 size={18}/>} onClick={() => go('Reporting')} color="grape" variant="light"/><NavLink active={area === 'Admin'} label="Admin" leftSection={<Settings size={18}/>} onClick={() => go('Admin')} color="grape" variant="light"/></Stack></AppShell.Navbar>
    <AppShell.Main><Box className="boutique-page">{error && <Alert color="red" mb="md" title="Unable to load operations">We couldn't connect to BoutiqueOS. Please try again.</Alert>}{area === 'Dashboard' && <Dashboard dashboard={dashboard} onNavigate={go} />}{area === 'Products' && <CatalogWorkspaceV3 />}{area === 'Customers' && <CustomersWorkspace customers={customers} onCreated={handleCustomerCreated} />}{area === 'Orders' && <GuidedOrdersWorkspaceV3 customers={customers} orders={orders} onCreated={refreshOperations} />}{area === 'Measurements' && <VisualMeasurementsWorkspaceV3 customers={customers} />}{area === 'Tailoring' && <TailoringWorkspace />}{area === 'Reporting' && <Reporting dashboard={dashboard} orders={orders} />}{area === 'Admin' && <Stack gap="lg"><Box><Text size="sm" c="dimmed">Admin</Text><Title order={1}>Settings & connections</Title></Box><TenantSettingsPanel/><SimpleGrid cols={{ base: 1, md: 2 }}><Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Store size={18} /></ThemeIcon><Box><Text fw={700}>Boutique</Text><Text size="sm" c="dimmed">Meera Boutique</Text></Box></Group></Card><Card withBorder padding="lg"><Group><ThemeIcon variant="light" color="grape"><Users size={18} /></ThemeIcon><Box><Text fw={700}>Staff & access</Text><Text size="sm" c="dimmed">User administration will live here.</Text></Box></Group></Card></SimpleGrid><IntegrationsPanel /></Stack>}</Box></AppShell.Main>
    <Box className="mobile-bottom-nav" hiddenFrom="md">{nav.slice(0, 5).map((item) => { const Icon = item.icon; return <button key={item.area} className={area === item.area ? 'active' : ''} onClick={() => go(item.area)}><Icon size={19}/><span>{item.area === 'Dashboard' ? 'Home' : item.label}</span></button> })}</Box>
  </AppShell>
}
