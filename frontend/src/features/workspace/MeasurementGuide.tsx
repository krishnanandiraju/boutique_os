import { Box, Group, Paper, SegmentedControl, Stack, Text, ThemeIcon, UnstyledButton } from '@mantine/core'
import { useMemo, useState } from 'react'
import { Ruler } from 'lucide-react'

type GarmentPreset = 'BLOUSE' | 'KURTA' | 'BOTTOM' | 'GENERAL'
type View = 'FRONT' | 'BACK'

type GuideField = { key: string; label: string; hint: string; view: View }

const guideFields: Record<GarmentPreset, GuideField[]> = {
  BLOUSE: [
    { key: 'bust', label: 'Bust', hint: 'Around the fullest part of the bust', view: 'FRONT' },
    { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' },
    { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' },
    { key: 'blouse_length', label: 'Blouse length', hint: 'Shoulder to desired blouse length', view: 'FRONT' },
    { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to desired sleeve end', view: 'FRONT' },
    { key: 'armhole', label: 'Armhole', hint: 'Around the armhole at the underarm', view: 'FRONT' },
    { key: 'front_neck_depth', label: 'Front neck depth', hint: 'Shoulder line to desired front neckline', view: 'FRONT' },
    { key: 'back_neck_depth', label: 'Back neck depth', hint: 'Shoulder line to desired back neckline', view: 'BACK' },
  ],
  KURTA: [
    { key: 'bust', label: 'Bust', hint: 'Around the fullest part of the bust', view: 'FRONT' },
    { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' },
    { key: 'hip', label: 'Hip', hint: 'Around the fullest part of the hip', view: 'FRONT' },
    { key: 'shoulder', label: 'Shoulder', hint: 'Shoulder tip to shoulder tip', view: 'BACK' },
    { key: 'kurta_length', label: 'Kurta length', hint: 'Shoulder to desired hem', view: 'FRONT' },
    { key: 'sleeve_length', label: 'Sleeve length', hint: 'Shoulder point to desired sleeve end', view: 'FRONT' },
    { key: 'armhole', label: 'Armhole', hint: 'Around the armhole at the underarm', view: 'FRONT' },
  ],
  BOTTOM: [
    { key: 'waist', label: 'Waist', hint: 'Around the natural waist', view: 'FRONT' },
    { key: 'hip', label: 'Hip', hint: 'Around the fullest part of the hip', view: 'FRONT' },
    { key: 'length', label: 'Length', hint: 'Waist to desired hem', view: 'FRONT' },
    { key: 'thigh', label: 'Thigh', hint: 'Around the fullest upper thigh', view: 'FRONT' },
    { key: 'bottom_opening', label: 'Bottom opening', hint: 'Across the desired leg opening', view: 'FRONT' },
  ],
  GENERAL: [],
}

const linePositions: Record<string, { x1: number; y1: number; x2: number; y2: number }> = {
  bust: { x1: 30, y1: 38, x2: 70, y2: 38 },
  waist: { x1: 34, y1: 50, x2: 66, y2: 50 },
  hip: { x1: 31, y1: 62, x2: 69, y2: 62 },
  shoulder: { x1: 34, y1: 24, x2: 66, y2: 24 },
  blouse_length: { x1: 38, y1: 24, x2: 38, y2: 53 },
  kurta_length: { x1: 38, y1: 24, x2: 38, y2: 78 },
  sleeve_length: { x1: 67, y1: 26, x2: 79, y2: 45 },
  armhole: { x1: 66, y1: 29, x2: 70, y2: 40 },
  front_neck_depth: { x1: 50, y1: 24, x2: 50, y2: 34 },
  back_neck_depth: { x1: 50, y1: 24, x2: 50, y2: 31 },
  length: { x1: 39, y1: 47, x2: 39, y2: 91 },
  thigh: { x1: 35, y1: 65, x2: 50, y2: 65 },
  bottom_opening: { x1: 35, y1: 90, x2: 49, y2: 90 },
}

function GarmentFigure({ garment, activeField, view }: { garment: GarmentPreset; activeField: string | null; view: View }) {
  const fields = guideFields[garment].filter((field) => field.view === view)
  const bodyPath = garment === 'BOTTOM'
    ? 'M38 18 L62 18 L66 48 L61 92 L50 92 L50 50 L48 92 L37 92 L34 48 Z'
    : garment === 'KURTA'
      ? 'M38 20 Q50 14 62 20 L76 32 L68 43 L63 36 L66 88 L34 88 L37 36 L32 43 L24 32 Z'
      : 'M38 22 Q50 16 62 22 L76 32 L69 45 L63 37 L65 55 L35 55 L37 37 L31 45 L24 32 Z'

  return (
    <svg className="measurement-guide-svg" viewBox="0 0 100 100" role="img" aria-label={`${garment.toLowerCase()} ${view.toLowerCase()} measurement diagram`}>
      <path d={bodyPath} className="garment-silhouette" />
      {garment !== 'BOTTOM' && (
        <>
          <circle cx="50" cy="11" r="7" className="garment-head" />
          <path d="M47 18 L47 22 M53 18 L53 22" className="garment-detail" />
        </>
      )}
      {fields.map((field) => {
        const position = linePositions[field.key]
        if (!position) return null
        const active = activeField === field.key
        const number = guideFields[garment].findIndex((candidate) => candidate.key === field.key) + 1
        return (
          <g key={field.key} className={active ? 'guide-line active' : 'guide-line'}>
            <line x1={position.x1} y1={position.y1} x2={position.x2} y2={position.y2} />
            <circle cx={position.x2} cy={position.y2} r="3.5" />
            <text x={position.x2} y={position.y2 + 1.4} textAnchor="middle">{number}</text>
          </g>
        )
      })}
    </svg>
  )
}

export function MeasurementGuide({ garment, activeField, onSelectField }: { garment: GarmentPreset; activeField: string | null; onSelectField: (key: string) => void }) {
  const [view, setView] = useState<View>('FRONT')
  const fields = useMemo(() => guideFields[garment], [garment])

  if (garment === 'GENERAL') {
    return (
      <Paper withBorder p="lg">
        <Group>
          <ThemeIcon color="grape" variant="light"><Ruler size={18} /></ThemeIcon>
          <Text c="dimmed">Choose Blouse, Kurta or Bottom for a visual measurement guide.</Text>
        </Group>
      </Paper>
    )
  }

  return (
    <Paper withBorder p="lg" className="measurement-guide-card">
      <Group justify="space-between" align="center" mb="md">
        <Box>
          <Text fw={800}>Measurement guide</Text>
          <Text size="sm" c="dimmed">Select a measurement to see where it is taken.</Text>
        </Box>
        <SegmentedControl
          size="xs"
          value={view}
          onChange={(value) => setView(value as View)}
          data={[{ label: 'Front', value: 'FRONT' }, { label: 'Back', value: 'BACK' }]}
        />
      </Group>

      <Box className="measurement-figure">
        <GarmentFigure garment={garment} activeField={activeField} view={view} />
      </Box>

      <Stack gap={4} mt="md">
        {fields.map((field, index) => (
          <UnstyledButton
            key={field.key}
            className={activeField === field.key ? 'guide-instruction active' : 'guide-instruction'}
            onClick={() => {
              onSelectField(field.key)
              setView(field.view)
            }}
          >
            <Group gap="sm" wrap="nowrap">
              <span className="guide-number">{index + 1}</span>
              <Box>
                <Text size="sm" fw={700}>{field.label}</Text>
                <Text size="xs" c="dimmed">{field.hint}{field.view === 'BACK' ? ' · Back view' : ''}</Text>
              </Box>
            </Group>
          </UnstyledButton>
        ))}
      </Stack>
    </Paper>
  )
}
