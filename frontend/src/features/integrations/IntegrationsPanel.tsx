import { useEffect, useMemo, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import {
  BarChart3,
  Bot,
  Box as BoxIcon,
  CalendarDays,
  ChevronRight,
  Cloud,
  Download,
  FileImage,
  FileText,
  Link2,
  Mail,
  Palette,
  Printer,
  RefreshCw,
  Scissors,
  Settings2,
  Shapes,
  Sparkles,
  WalletCards,
} from 'lucide-react'
import { api } from '../../api'
import type { IntegrationOutboxItem, IntegrationOutboxStatus } from '../../types'

type IntegrationCategory = 'ALL' | 'DESIGN' | 'OPERATIONS' | 'BUSINESS' | 'DATA'
type IntegrationStatus = 'CONNECTED' | 'NOT_CONFIGURED' | 'AVAILABLE'

type IntegrationSurface = {
  name: string
  description: string
  category: Exclude<IntegrationCategory, 'ALL'>
  status: IntegrationStatus
  icon: typeof Palette
}

const surfaces: IntegrationSurface[] = [
  { name: 'Figma', description: 'Design collections, tech packs and shared design references.', category: 'DESIGN', status: 'NOT_CONFIGURED', icon: Shapes },
  { name: 'CLO 3D', description: '3D garment design, fit visualization and sampling workflows.', category: 'DESIGN', status: 'NOT_CONFIGURED', icon: BoxIcon },
  { name: 'Adobe Creative Cloud', description: 'Product photography, artwork and creative assets.', category: 'DESIGN', status: 'NOT_CONFIGURED', icon: FileImage },
  { name: 'Canva', description: 'Lookbooks, catalogues and boutique marketing creatives.', category: 'DESIGN', status: 'NOT_CONFIGURED', icon: Palette },

  { name: 'Barcode & Label Printing', description: 'Print product tags, barcodes and garment labels.', category: 'OPERATIONS', status: 'AVAILABLE', icon: Printer },
  { name: 'Calendar', description: 'Schedule measurements, trials, pickups and due dates.', category: 'OPERATIONS', status: 'NOT_CONFIGURED', icon: CalendarDays },
  { name: 'Tailoring Workforce', description: 'Connect external tailoring teams and production partners.', category: 'OPERATIONS', status: 'AVAILABLE', icon: Scissors },
  { name: 'Google Drive', description: 'Store product photos, references, lookbooks and documents.', category: 'OPERATIONS', status: 'NOT_CONFIGURED', icon: Cloud },

  { name: 'Tally', description: 'Accounting and GST hand-off for completed business transactions.', category: 'BUSINESS', status: 'NOT_CONFIGURED', icon: WalletCards },
  { name: 'Zoho Books', description: 'Invoice and accounting synchronization for finance teams.', category: 'BUSINESS', status: 'NOT_CONFIGURED', icon: FileText },
  { name: 'Email (SMTP)', description: 'Send order updates, receipts and internal notifications.', category: 'BUSINESS', status: 'NOT_CONFIGURED', icon: Mail },
  { name: 'Business Export', description: 'Export orders, customers and inventory for downstream systems.', category: 'BUSINESS', status: 'AVAILABLE', icon: Download },

  { name: 'Analytics', description: 'Sales, products, customer and operational insight feeds.', category: 'DATA', status: 'AVAILABLE', icon: BarChart3 },
  { name: 'AI Design Assistant', description: 'Future design ideation and collection-assist workflows.', category: 'DATA', status: 'AVAILABLE', icon: Sparkles },
  { name: 'Data Export API', description: 'Programmatic export for reporting and data platforms.', category: 'DATA', status: 'AVAILABLE', icon: Bot },
  { name: 'Webhooks', description: 'Trigger internal tools and workflows from BoutiqueOS events.', category: 'DATA', status: 'AVAILABLE', icon: Link2 },
]

const categoryLabels: Record<IntegrationCategory, string> = {
  ALL: 'All integrations',
  DESIGN: 'Design & Product',
  OPERATIONS: 'Operations',
  BUSINESS: 'Business Systems',
  DATA: 'Data & AI',
}

function prettyStatus(status: string): string {
  return status.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function eventLabel(eventType: string): { title: string; explanation: string } {
  if (eventType === 'order.created') {
    return { title: 'Order committed', explanation: 'The order is safely recorded and ready for downstream processing.' }
  }
  if (eventType === 'inventory.changed') {
    return { title: 'Inventory changed', explanation: 'Physical inventory truth changed and an integration event was recorded.' }
  }
  return { title: eventType.replaceAll('.', ' · '), explanation: 'Durable integration event recorded after the BoutiqueOS transaction.' }
}

function SurfaceCard({ surface }: { surface: IntegrationSurface }) {
  const Icon = surface.icon
  const connected = surface.status === 'CONNECTED'
  const available = surface.status === 'AVAILABLE'

  return (
    <Card withBorder padding="md" radius="lg" className="integration-surface-card">
      <Stack gap="md" h="100%">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group align="flex-start" wrap="nowrap">
            <ThemeIcon size={44} radius="md" variant="light" color="grape"><Icon size={21} /></ThemeIcon>
            <Box>
              <Text fw={800}>{surface.name}</Text>
              <Text size="sm" c="dimmed" mt={2}>{surface.description}</Text>
            </Box>
          </Group>
          <ChevronRight size={17} color="var(--mantine-color-gray-5)" />
        </Group>

        <Group justify="space-between" mt="auto">
          <Badge
            variant="light"
            color={connected ? 'teal' : available ? 'grape' : 'gray'}
            leftSection={<span className={`integration-status-dot ${connected ? 'connected' : available ? 'available' : ''}`} />}
          >
            {connected ? 'Connected' : available ? 'Available' : 'Not configured'}
          </Badge>
          <Button size="xs" variant={connected ? 'light' : 'outline'} color="grape" leftSection={connected ? <Settings2 size={14} /> : undefined}>
            {connected ? 'Manage' : available ? 'Set up' : 'Configure'}
          </Button>
        </Group>
      </Stack>
    </Card>
  )
}

export function IntegrationsPanel() {
  const [outbox, setOutbox] = useState<IntegrationOutboxItem[]>([])
  const [category, setCategory] = useState<IntegrationCategory>('ALL')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void api.integrationOutbox()
      .then((result) => { if (active) setOutbox(result) })
      .catch((err) => { if (active) setError(err instanceof Error ? err.message : 'Unable to load integration activity') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const filtered = useMemo(() => category === 'ALL' ? surfaces : surfaces.filter((surface) => surface.category === category), [category])
  const pending = outbox.filter((event) => event.status === 'PENDING').length
  const failed = outbox.filter((event) => event.status === 'FAILED').length

  async function refresh() {
    setError('')
    try {
      setOutbox(await api.integrationOutbox())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to refresh integration activity')
    }
  }

  async function retryEvent(event: IntegrationOutboxItem) {
    setError('')
    try {
      const updated = await api.retryIntegrationOutboxItem(event.id)
      setOutbox((current) => current.map((row) => row.id === updated.id ? updated : row))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to retry event')
    }
  }

  return (
    <Stack gap="xl" className="integrations-v2">
      <Group justify="space-between" align="flex-end">
        <Box>
          <Text size="sm" c="dimmed">Admin · Integrations</Text>
          <Title order={2}>Integrations & surfaces</Title>
          <Text c="dimmed" mt={4}>Connect the tools and business systems your boutique already uses.</Text>
        </Box>
        <Group>
          <Button variant="default" leftSection={<FileText size={16} />}>API docs</Button>
          <Button color="grape" leftSection={<Link2 size={16} />}>Add integration</Button>
        </Group>
      </Group>

      <SegmentedControl
        value={category}
        onChange={(value) => setCategory(value as IntegrationCategory)}
        data={Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))}
        color="grape"
        radius="md"
        className="integration-category-control"
      />

      {error && <Alert color="red" title="Integration activity unavailable">{error}</Alert>}

      <SimpleGrid cols={{ base: 1, sm: 2, xl: 4 }} spacing="md">
        {filtered.map((surface) => <SurfaceCard key={surface.name} surface={surface} />)}
      </SimpleGrid>

      <Card withBorder padding="lg" radius="lg" className="integration-activity-card">
        <Group justify="space-between" mb="md">
          <Box>
            <Group gap="xs"><Title order={3}>Integration activity</Title>{(pending > 0 || failed > 0) && <Badge color={failed ? 'red' : 'orange'}>{failed ? `${failed} need attention` : `${pending} pending`}</Badge>}</Group>
            <Text size="sm" c="dimmed">Durable events generated by BoutiqueOS business transactions.</Text>
          </Box>
          <ActionIcon variant="light" color="grape" size="lg" onClick={() => void refresh()} aria-label="Refresh integration activity"><RefreshCw size={17} /></ActionIcon>
        </Group>

        {loading && <Text size="sm" c="dimmed">Loading activity…</Text>}
        {!loading && outbox.length === 0 && <Box className="integration-empty-state"><ThemeIcon size={44} radius="xl" variant="light" color="grape"><Link2 size={20} /></ThemeIcon><Text fw={700}>No integration activity yet</Text><Text size="sm" c="dimmed">Events will appear here when orders, inventory or connected systems generate activity.</Text></Box>}

        <Stack gap="sm">
          {outbox.slice(0, 8).map((event) => {
            const presentation = eventLabel(event.event_type)
            return <Card key={event.id} withBorder padding="sm" radius="md">
              <Group justify="space-between" align="center" wrap="nowrap">
                <Box>
                  <Group gap="xs"><Text fw={700}>{presentation.title}</Text><Badge size="xs" variant="light" color={event.status === 'FAILED' ? 'red' : event.status === 'PROCESSED' ? 'teal' : 'gray'}>{prettyStatus(event.status)}</Badge></Group>
                  <Text size="xs" c="dimmed" mt={2}>{presentation.explanation} · {event.aggregate_type} #{event.aggregate_id}</Text>
                </Box>
                {event.status === ('FAILED' as IntegrationOutboxStatus) && <Button size="xs" variant="light" color="red" onClick={() => void retryEvent(event)}>Retry</Button>}
              </Group>
            </Card>
          })}
        </Stack>
      </Card>
    </Stack>
  )
}
