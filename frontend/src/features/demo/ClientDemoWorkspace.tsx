import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  AppShell,
  Badge,
  Box,
  Burger,
  Button,
  Card,
  Group,
  NavLink,
  Paper,
  Select,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  Activity,
  BrainCircuit,
  CircleGauge,
  ExternalLink,
  HeartHandshake,
  PackageCheck,
  PlugZap,
  Scissors,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Store,
} from 'lucide-react'
import App from '../../App'
import { api } from '../../api'
import { IntegrationsPanel } from '../integrations/IntegrationsPanel'
import { StitchingPanel } from '../stitching'
import { DemoJourney } from './DemoJourney'
import type { AppNavKey } from '../../layout/AppShell'
import type { Customer, DashboardData } from '../../types'
import './client-demo.css'

type WorkspaceView = 'Overview' | 'Fit Memory' | 'Connections' | 'Operations'

const workspaceViews = [
  { key: 'Overview' as const, label: 'Overview', description: 'Business cockpit', icon: CircleGauge },
  { key: 'Operations' as const, label: 'Operations', description: 'Catalog to tailoring', icon: ShoppingBag },
  { key: 'Fit Memory' as const, label: 'Fit Memory', description: 'Learn every stitch', icon: BrainCircuit },
  { key: 'Connections' as const, label: 'Connections', description: 'Channels and systems', icon: PlugZap },
]

function money(value: string | number): string {
  const numeric = typeof value === 'string' ? Number(value) : value
  return `₹${numeric.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function MetricCard({ label, value, detail, icon: Icon, emphasized = false }: {
  label: string
  value: string | number
  detail: string
  icon: typeof Activity
  emphasized?: boolean
}) {
  return (
    <Card className={emphasized ? 'modern-metric-card emphasized' : 'modern-metric-card'} padding="lg" withBorder>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={4}>
          <Text size="xs" fw={700} c={emphasized ? 'white' : 'dimmed'} tt="uppercase" className="metric-label">{label}</Text>
          <Title order={3} c={emphasized ? 'white' : undefined}>{value}</Title>
          <Text size="xs" c={emphasized ? 'grape.0' : 'dimmed'}>{detail}</Text>
        </Stack>
        <ThemeIcon variant={emphasized ? 'white' : 'light'} color="grape" size={42} radius="md">
          <Icon size={21} />
        </ThemeIcon>
      </Group>
    </Card>
  )
}

export default function ClientDemoWorkspace() {
  const [view, setView] = useState<WorkspaceView>('Overview')
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [opened, { toggle, close }] = useDisclosure(false)

  useEffect(() => {
    let active = true
    void Promise.all([api.dashboard(), api.customers()])
      .then(([dashboardResult, customerResult]) => {
        if (!active) return
        setDashboard(dashboardResult)
        setCustomers(customerResult)
        setSelectedCustomerId((current) => current ?? customerResult[0]?.id ?? null)
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : 'Unable to load demo workspace'))
      .finally(() => active && setLoading(false))

    return () => {
      active = false
    }
  }, [])

  const selectedCustomer = useMemo(
    () => customers.find((customer) => customer.id === selectedCustomerId) || null,
    [customers, selectedCustomerId],
  )

  function navigate(next: WorkspaceView) {
    setView(next)
    close()
  }

  function handleJourneyNavigation(target: AppNavKey) {
    if (target === 'Fit Memory' || target === 'Customers') {
      navigate('Fit Memory')
      return
    }
    if (target === 'Integrations') {
      navigate('Connections')
      return
    }
    navigate('Operations')
  }

  return (
    <AppShell
      header={{ height: 68 }}
      navbar={{ width: 272, breakpoint: 'md', collapsed: { mobile: !opened } }}
      padding="md"
      className="modern-workspace"
    >
      <AppShell.Header className="modern-header">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label="Open navigation" />
            <ThemeIcon size={40} radius="md" variant="gradient" gradient={{ from: 'grape', to: 'violet', deg: 135 }}>
              <Store size={21} />
            </ThemeIcon>
            <Box>
              <Group gap={8} wrap="nowrap">
                <Text fw={800} size="lg">BoutiqueOS</Text>
                <Badge size="xs" variant="light" color="grape">Demo</Badge>
              </Group>
              <Text size="xs" c="dimmed" visibleFrom="sm">Meera Boutique · Retail, tailoring and fit intelligence</Text>
            </Box>
          </Group>
          <Group gap="xs">
            <Badge variant="dot" color="teal" visibleFrom="sm">Operational truth online</Badge>
            <Button variant="subtle" color="dark" leftSection={<ExternalLink size={16} />} onClick={() => navigate('Operations')} visibleFrom="sm">
              Open operations
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" className="modern-navbar">
        <Stack h="100%" gap="lg">
          <Box>
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb="xs">Workspace</Text>
            <Stack gap={4}>
              {workspaceViews.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.key}
                    active={view === item.key}
                    label={item.label}
                    description={item.description}
                    leftSection={<Icon size={18} strokeWidth={1.8} />}
                    onClick={() => navigate(item.key)}
                    color="grape"
                    variant="light"
                    className="modern-nav-link"
                  />
                )
              })}
            </Stack>
          </Box>

          <Paper mt="auto" p="md" withBorder className="merchant-card">
            <Group gap="sm" wrap="nowrap">
              <ThemeIcon variant="light" color="teal" radius="xl"><ShieldCheck size={17} /></ThemeIcon>
              <Box>
                <Text size="xs" c="dimmed">Demo merchant</Text>
                <Text fw={700} size="sm">Meera Boutique</Text>
              </Box>
            </Group>
            <Text size="xs" c="dimmed" mt="sm" lh={1.5}>
              BoutiqueOS owns inventory, customer, order and stitch truth. Channels remain replaceable.
            </Text>
          </Paper>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <Box className="modern-page">
          <Group justify="space-between" align="flex-end" mb="lg">
            <Box>
              <Text size="xs" fw={700} c="grape.6" tt="uppercase" className="page-kicker">Client demonstration workspace</Text>
              <Title order={1}>{view}</Title>
            </Box>
            <Badge size="lg" variant="light" color="grape" visibleFrom="sm">Demo mode</Badge>
          </Group>

          {error && <Alert color="red" mb="md" title="Workspace unavailable">{error}</Alert>}

          {view === 'Overview' && (
            <Stack gap="lg">
              <Paper className="modern-hero" p={{ base: 'lg', md: 'xl' }} withBorder>
                <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="xl">
                  <Stack gap="md" justify="center">
                    <Badge variant="light" color="grape" leftSection={<Sparkles size={13} />}>Boutique operating system</Badge>
                    <Title order={2} className="modern-hero-title">Sell the exact piece. Stitch it right. Remember what the customer actually liked.</Title>
                    <Text c="dimmed" size="lg" maw={760} lh={1.65}>
                      One operating layer for unique merchandise, fabric rolls, customer measurements, orders, tailoring and the fit knowledge that makes repeat business better.
                    </Text>
                    <Group>
                      <Button size="md" color="grape" onClick={() => navigate('Operations')} leftSection={<ShoppingBag size={18} />}>Run boutique operations</Button>
                      <Button size="md" variant="light" color="grape" onClick={() => navigate('Fit Memory')} leftSection={<BrainCircuit size={18} />}>Show Fit Memory</Button>
                    </Group>
                  </Stack>

                  <Stack gap="sm" justify="center">
                    <Paper className="proof-card" p="md" withBorder>
                      <Group wrap="nowrap" align="flex-start"><ThemeIcon color="teal" variant="light"><PackageCheck size={18} /></ThemeIcon><Box><Text fw={700}>Unique inventory protected</Text><Text size="sm" c="dimmed">Hold the exact piece and prevent double-selling.</Text></Box></Group>
                    </Paper>
                    <Paper className="proof-card" p="md" withBorder>
                      <Group wrap="nowrap" align="flex-start"><ThemeIcon color="violet" variant="light"><HeartHandshake size={18} /></ThemeIcon><Box><Text fw={700}>Measurements remain historical</Text><Text size="sm" c="dimmed">Every order can retain the measurement version actually used.</Text></Box></Group>
                    </Paper>
                    <Paper className="proof-card" p="md" withBorder>
                      <Group wrap="nowrap" align="flex-start"><ThemeIcon color="grape" variant="light"><BrainCircuit size={18} /></ThemeIcon><Box><Text fw={700}>Fit feedback becomes memory</Text><Text size="sm" c="dimmed">Sleeve too long. Neckline too deep. Learn without rewriting history.</Text></Box></Group>
                    </Paper>
                  </Stack>
                </SimpleGrid>
              </Paper>

              {loading ? (
                <SimpleGrid cols={{ base: 2, sm: 3, xl: 6 }}><Skeleton h={124} /><Skeleton h={124} /><Skeleton h={124} /><Skeleton h={124} /><Skeleton h={124} /><Skeleton h={124} /></SimpleGrid>
              ) : dashboard && (
                <SimpleGrid cols={{ base: 2, sm: 3, xl: 6 }} spacing="sm">
                  <MetricCard label="Sales today" value={money(dashboard.sales_today)} detail="Operating snapshot" icon={Activity} emphasized />
                  <MetricCard label="Available" value={dashboard.available_items} detail="Ready to sell" icon={PackageCheck} />
                  <MetricCard label="Held pieces" value={dashboard.held_items} detail="Protected inventory" icon={ShieldCheck} />
                  <MetricCard label="Pending orders" value={dashboard.orders_pending} detail="Need action" icon={ShoppingBag} />
                  <MetricCard label="Tailoring" value={dashboard.tailoring_pending} detail="In workflow" icon={Scissors} />
                  <MetricCard label="Remnants" value={dashboard.remnant_rolls} detail="Fabric still visible" icon={Store} />
                </SimpleGrid>
              )}

              <DemoJourney onNavigate={handleJourneyNavigation} />

              <Paper p="lg" withBorder className="modern-architecture">
                <Stack gap="md">
                  <Box><Text size="xs" fw={700} c="grape.6" tt="uppercase">Architecture promise</Text><Title order={3}>BoutiqueOS owns truth. Workflow and channels orchestrate around it.</Title></Box>
                  <SimpleGrid cols={{ base: 1, md: 3 }}>
                    <Card withBorder><Text fw={700}>BoutiqueOS Core</Text><Text size="sm" c="dimmed">Inventory · customers · measurements · orders · stitch records</Text></Card>
                    <Card withBorder><Text fw={700}>Transactional Outbox</Text><Text size="sm" c="dimmed">Durable events · retries · idempotency · delivery state</Text></Card>
                    <Card withBorder><Text fw={700}>Workflow & Integrations</Text><Text size="sm" c="dimmed">Temporal later · Labha · Shopify · WhatsApp · ERP</Text></Card>
                  </SimpleGrid>
                </Stack>
              </Paper>
            </Stack>
          )}

          {view === 'Operations' && (
            <Stack gap="md">
              <Paper p="md" withBorder className="section-intro">
                <Group justify="space-between" align="center">
                  <Box><Text size="xs" fw={700} c="grape.6" tt="uppercase">Operational workspace</Text><Title order={3}>Catalog, customers, orders, lots and tailoring</Title></Box>
                  <Badge variant="light" color="teal">Existing workflows preserved</Badge>
                </Group>
              </Paper>
              <Box className="embedded-operations modern-embedded-operations"><App /></Box>
            </Stack>
          )}

          {view === 'Fit Memory' && (
            <Stack gap="lg">
              <Paper p="lg" withBorder className="section-intro">
                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
                  <Box>
                    <Text size="xs" fw={700} c="grape.6" tt="uppercase">Customer intelligence that stays with the boutique</Text>
                    <Title order={2}>Measurement Book + Stitch Feedback = Fit Memory</Title>
                    <Text c="dimmed" mt="sm" lh={1.6}>Measurements capture the body. Stitch records capture what was made. Trial feedback captures how it felt. Keeping those facts separate makes the history trustworthy.</Text>
                  </Box>
                  <Select
                    label="Customer"
                    description="Choose whose fit history you want to review"
                    value={selectedCustomerId?.toString() ?? null}
                    onChange={(value) => setSelectedCustomerId(value ? Number(value) : null)}
                    data={customers.map((customer) => ({ value: customer.id.toString(), label: `${customer.name} · ${customer.phone}` }))}
                    searchable
                    size="md"
                    style={{ alignSelf: 'end' }}
                  />
                </SimpleGrid>
              </Paper>

              <SimpleGrid cols={{ base: 1, md: 3 }}>
                <Card withBorder><Text size="xs" c="grape.6" fw={700} tt="uppercase">Body fact</Text><Text fw={700} mt={4}>Measurement version</Text><Text size="sm" c="dimmed">Immutable historical dimensions used for an order.</Text></Card>
                <Card withBorder><Text size="xs" c="violet.6" fw={700} tt="uppercase">Stitch fact</Text><Text fw={700} mt={4}>Stitch record</Text><Text size="sm" c="dimmed">Garment, tailor, stage and exact measurement version used.</Text></Card>
                <Card withBorder><Text size="xs" c="teal.7" fw={700} tt="uppercase">Learned signal</Text><Text fw={700} mt={4}>Trial feedback</Text><Text size="sm" c="dimmed">Structured observations such as sleeve too long or neck too deep.</Text></Card>
              </SimpleGrid>

              {selectedCustomer ? <StitchingPanel customerId={selectedCustomer.id} customerName={selectedCustomer.name} /> : <Alert color="grape">Create or select a customer to start building Fit Memory.</Alert>}
            </Stack>
          )}

          {view === 'Connections' && (
            <Stack gap="lg">
              <Paper p="lg" withBorder className="section-intro">
                <Group justify="space-between" align="flex-start" gap="xl">
                  <Box maw={800}>
                    <Text size="xs" fw={700} c="grape.6" tt="uppercase">Composable commerce</Text>
                    <Title order={2}>Connect selling, money, logistics and messaging without surrendering boutique truth.</Title>
                    <Text c="dimmed" mt="sm" lh={1.6}>Integration events remain durable. Long-running business workflows belong behind the workflow port instead of growing a home-built queue.</Text>
                  </Box>
                  <ThemeIcon size={52} radius="lg" variant="light" color="grape" visibleFrom="md"><PlugZap size={26} /></ThemeIcon>
                </Group>
              </Paper>
              <IntegrationsPanel />
            </Stack>
          )}
        </Box>
      </AppShell.Main>
    </AppShell>
  )
}
