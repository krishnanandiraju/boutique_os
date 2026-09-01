export type StitchRecordStatus =
  | 'DRAFT'
  | 'MEASURED'
  | 'CUTTING'
  | 'STITCHING'
  | 'TRIAL'
  | 'ALTERATION'
  | 'READY'
  | 'DELIVERED'
  | 'CLOSED'

export type FitArea =
  | 'OVERALL'
  | 'BUST'
  | 'WAIST'
  | 'HIP'
  | 'SHOULDER'
  | 'ARMHOLE'
  | 'SLEEVE'
  | 'NECKLINE'
  | 'LENGTH'
  | 'BOTTOM_OPENING'
  | 'CROTCH'
  | 'OTHER'

export type FitDirection =
  | 'TOO_LONG'
  | 'TOO_SHORT'
  | 'TOO_TIGHT'
  | 'TOO_LOOSE'
  | 'TOO_DEEP'
  | 'TOO_SHALLOW'
  | 'TOO_HIGH'
  | 'TOO_LOW'
  | 'OTHER'

export type FeedbackSeverity = 'MINOR' | 'MODERATE' | 'MAJOR'

export type GarmentTypeDefinition = {
  code: string
  display_name: string
  measurement_fields: string[]
  fit_areas: FitArea[]
  active: boolean
}

export type StitchFeedback = {
  id: number
  stitch_record_id: number
  fit_area: FitArea
  direction: FitDirection
  severity: FeedbackSeverity
  adjustment_value: string | null
  adjustment_unit: string | null
  comment: string | null
  resolved: boolean
  created_at: string
}

export type StitchRecord = {
  id: number
  merchant_id: number
  customer_id: number
  order_line_id: number | null
  measurement_profile_id: number | null
  measurement_version_id: number | null
  garment_type_code: string
  status: StitchRecordStatus
  tailor_name: string | null
  style_notes: string | null
  fit_notes: string | null
  created_at: string
  updated_at: string
  feedback: StitchFeedback[]
}

export type CustomerFitInsight = {
  customer_id: number
  garment_type_code: string
  recurring_feedback: string[]
  unresolved_feedback_count: number
  last_stitch_record_id: number | null
}
