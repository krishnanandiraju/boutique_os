export type InventoryType = 'UNIQUE' | 'STOCKED' | 'YARDAGE'

export type Availability = 'AVAILABLE' | 'HELD' | 'SOLD' | 'OUT_OF_STOCK' | 'UNAVAILABLE'

export type OrderStatus =
  | 'DRAFT'
  | 'CONFIRMED'
  | 'TAILORING'
  | 'READY'
  | 'PACKED'
  | 'SHIPPED'
  | 'DELIVERED'
  | 'CANCELLED'

export type TailoringStage =
  | 'MEASUREMENT_PENDING'
  | 'CUTTING'
  | 'STITCHING'
  | 'QC'
  | 'TRIAL_SCHEDULED'
  | 'ALTERATION'
  | 'READY'

export type MeasurementUnit = 'INCH' | 'CM'

export type DashboardData = {
  sales_today: string
  available_items: number
  held_items: number
  orders_pending: number
  tailoring_pending: number
  low_stock_items: number
  remnant_rolls: number
}

export type Item = {
  id: number
  merchant_id: number
  name: string
  sku: string | null
  inventory_type: InventoryType
  category: string
  fabric: string | null
  color: string | null
  selling_price: string
  cost_price: string | null
  published: boolean
  created_at: string
  availability: Availability
  hold_expires_at: string | null
  quantity_available: string
}

export type Customer = {
  id: number
  merchant_id: number
  name: string
  phone: string
  email: string | null
  notes: string | null
}

export type InventoryStatus = 'AVAILABLE' | 'HELD' | 'SOLD' | 'DEPLETED' | 'REMNANT'

export type InventoryMovementType =
  | 'RECEIPT'
  | 'SALE'
  | 'ADJUSTMENT_IN'
  | 'ADJUSTMENT_OUT'
  | 'DAMAGE'
  | 'GIFT'
  | 'RETURN'
  | 'YARDAGE_CUT'
  | 'HOLD'
  | 'HOLD_RELEASE'
  | 'HOLD_EXPIRE'

export type ApiError = {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

export type OrderLineAllocation = {
  id: number
  order_line_id: number
  inventory_lot_id: number
  lot_code: string | null
  quantity: string
  created_at: string
}

export type OrderLine = {
  id: number
  item_id: number
  item_name: string | null
  inventory_lot_id: number | null
  measurement_profile_id: number | null
  measurement_version_id: number | null
  measurement_profile_name: string | null
  measurement_garment_type: string | null
  measurement_unit: MeasurementUnit | null
  measurement_values: Record<string, number> | null
  measurement_version_number: number | null
  allocations: OrderLineAllocation[]
  quantity: string
  unit_price: string
  line_total: string
  requires_tailoring: boolean
  tailoring_stage: TailoringStage | null
}

export type InventoryState = {
  item_id: number
  item_name: string
  inventory_type: InventoryType
  status: InventoryStatus
  quantity_available: string
}

export type InventoryLot = {
  id: number
  item_id: number
  lot_code: string | null
  quantity: string
  original_quantity: string
  status: InventoryStatus
  received_at: string
  cost_price: string | null
  notes: string | null
  created_at: string
}

export type InventoryMovement = {
  id: number
  merchant_id: number
  item_id: number
  inventory_lot_id: number
  movement_type: InventoryMovementType
  quantity: string
  reference_type: string | null
  reference_id: number | null
  reason: string | null
  created_at: string
}

export type Order = {
  id: number
  merchant_id: number
  customer_id: number
  status: OrderStatus
  total_amount: string
  created_at: string
  lines: OrderLine[]
  inventory_state?: InventoryState[]
}

export type TailoringLine = {
  id: number
  order_id: number
  item_name: string
  customer_name: string
  tailoring_stage: TailoringStage | null
}

export type MeasurementVersion = {
  id: number
  measurement_profile_id: number
  version_number: number
  measurements: Record<string, number>
  notes: string | null
  created_at: string
  created_by: string | null
}

export type MeasurementProfile = {
  id: number
  customer_id: number
  name: string
  garment_type: string | null
  unit: MeasurementUnit
  is_active: boolean
  created_at: string
  updated_at: string
  latest_version: MeasurementVersion | null
}

export type MeasurementProfileDetail = MeasurementProfile & {
  versions: MeasurementVersion[]
}

export type CommerceChannelType = 'BOUTIQUEOS' | 'LABHA' | 'SHOPIFY' | 'WHATSAPP' | 'INSTAGRAM' | 'MANUAL' | 'POS'

export type ChannelConnectionStatus = 'NOT_CONFIGURED' | 'CONNECTED' | 'DEGRADED' | 'ERROR'

export type IntegrationOutboxStatus = 'PENDING' | 'PROCESSING' | 'PROCESSED' | 'FAILED'

export type ChannelConnection = {
  id: number
  merchant_id: number
  channel_type: CommerceChannelType
  status: ChannelConnectionStatus
  external_account_id: string | null
  configuration_reference: string | null
  created_at: string
  updated_at: string
}

export type IntegrationOutboxItem = {
  id: number
  event_id: string
  merchant_id: number
  event_type: string
  aggregate_type: string
  aggregate_id: string
  payload_json: Record<string, unknown>
  status: IntegrationOutboxStatus
  attempt_count: number
  last_error: string | null
  created_at: string
  processed_at: string | null
  next_attempt_at: string | null
}

export type TailoringTask = {
  id: number
  order_line_id: number
  stage: TailoringStage
  assignee: string | null
  due_at: string | null
  priority: 'NORMAL' | 'URGENT'
  notes: string | null
  created_at: string
  updated_at: string
  customer_id: number
  customer_name: string
  order_id: number
  order_status: OrderStatus
  item_id: number
  item_name: string
  measurement_profile_id: number | null
  measurement_profile_name: string | null
  measurement_version_id: number | null
  measurement_version_number: number | null
  measurement_unit: MeasurementUnit | null
  measurement_values: Record<string, number> | null
}
