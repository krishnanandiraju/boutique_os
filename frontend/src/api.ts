import type {
  ChannelConnection,
  Customer,
  DashboardData,
  InventoryLot,
  InventoryMovement,
  InventoryMovementType,
  Item,
  IntegrationOutboxItem,
  MeasurementProfile,
  MeasurementProfileDetail,
  MeasurementVersion,
  Order,
  OrderStatus,
  TailoringTask,
  TailoringStage,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type ApiError = {
  error: { code: string; message: string; details?: Record<string, unknown> }
}

export type TailoringTransition = {
  task_id: number
  order_id: number
  stage: TailoringStage
  order_status: OrderStatus
  order_became_ready: boolean
  remaining_tailoring_items: number
}

function parseError(response: Response): Promise<Error> {
  return response.json().then((payload: ApiError | { detail?: string }) => {
    if (payload && typeof payload === 'object' && 'error' in payload && payload.error) return new Error(payload.error.message || payload.error.code || 'Request failed')
    if (payload && typeof payload === 'object' && 'detail' in payload && typeof payload.detail === 'string') return new Error(payload.detail)
    return new Error(`Request failed (${response.status})`)
  }).catch(() => new Error(response.statusText || 'Request failed'))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) }, ...init })
  if (!response.ok) throw await parseError(response)
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  dashboard: () => request<DashboardData>('/api/dashboard'),
  items: () => request<Item[]>('/api/items'),
  item: (itemId: number) => request<Item>(`/api/items/${itemId}`),
  addItem: (payload: { name: string; inventory_type: 'UNIQUE' | 'STOCKED' | 'YARDAGE'; category: string; fabric?: string; color?: string; selling_price: string; quantity: string }) => request<Item>('/api/items', { method: 'POST', body: JSON.stringify(payload) }),
  holdItem: (itemId: number, customer_id: number, ttl_hours = 24) => request(`/api/items/${itemId}/hold`, { method: 'POST', body: JSON.stringify({ customer_id, ttl_hours }) }),
  releaseHold: (itemId: number) => request(`/api/items/${itemId}/hold`, { method: 'DELETE' }),
  itemLots: (itemId: number) => request<InventoryLot[]>(`/api/items/${itemId}/lots`),
  receiveLot: (itemId: number, payload: { lot_code?: string; quantity: string; received_at?: string; cost_price?: string; notes?: string }) => request<InventoryLot>(`/api/items/${itemId}/lots`, { method: 'POST', body: JSON.stringify(payload) }),
  lot: (lotId: number) => request<InventoryLot>(`/api/inventory/lots/${lotId}`),
  adjustLot: (lotId: number, payload: { adjustment_type: InventoryMovementType; quantity: string; reason?: string }) => request<InventoryLot>(`/api/inventory/lots/${lotId}/adjust`, { method: 'POST', body: JSON.stringify(payload) }),
  inventoryMovements: (filters?: { item_id?: number; lot_id?: number; movement_type?: InventoryMovementType; reference_type?: string; since?: string; until?: string; limit?: number }) => {
    const params = new URLSearchParams()
    if (filters?.item_id != null) params.set('item_id', String(filters.item_id)); if (filters?.lot_id != null) params.set('lot_id', String(filters.lot_id)); if (filters?.movement_type) params.set('movement_type', filters.movement_type); if (filters?.reference_type) params.set('reference_type', filters.reference_type); if (filters?.since) params.set('since', filters.since); if (filters?.until) params.set('until', filters.until); if (filters?.limit != null) params.set('limit', String(filters.limit))
    const query = params.toString(); return request<InventoryMovement[]>(`/api/inventory/movements${query ? `?${query}` : ''}`)
  },
  customers: () => request<Customer[]>('/api/customers'),
  addCustomer: (payload: { name: string; phone: string; email?: string; notes?: string }) => request<Customer>('/api/customers', { method: 'POST', body: JSON.stringify(payload) }),
  customerMeasurementProfiles: (customerId: number) => request<MeasurementProfile[]>(`/api/customers/${customerId}/measurement-profiles`),
  createMeasurementProfile: (customerId: number, payload: { name: string; garment_type?: string; unit: 'INCH' | 'CM'; measurements: Record<string, string | number>; notes?: string; created_by?: string }) => request<MeasurementProfileDetail>(`/api/customers/${customerId}/measurement-profiles`, { method: 'POST', body: JSON.stringify(payload) }),
  measurementProfile: (profileId: number) => request<MeasurementProfileDetail>(`/api/measurement-profiles/${profileId}`),
  createMeasurementVersion: (profileId: number, payload: { measurements: Record<string, string | number>; notes?: string; created_by?: string }) => request<MeasurementVersion>(`/api/measurement-profiles/${profileId}/versions`, { method: 'POST', body: JSON.stringify(payload) }),
  measurementVersions: (profileId: number) => request<MeasurementVersion[]>(`/api/measurement-profiles/${profileId}/versions`),
  orders: () => request<Order[]>('/api/orders'),
  createOrder: (payload: { customer_id: number; lines: Array<{ item_id: number; quantity: string; requires_tailoring: boolean; measurement_profile_id?: number; measurement_version_id?: number }> }) => request<Order>('/api/orders', { method: 'POST', body: JSON.stringify(payload) }),
  updateOrderStatus: (orderId: number, status: OrderStatus) => request<Order>(`/api/orders/${orderId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  tailoringTasks: (filters?: { stage?: TailoringStage; assignee?: string; due?: 'overdue' | 'today' | 'upcoming' }) => {
    const params = new URLSearchParams(); if (filters?.stage) params.set('stage', filters.stage); if (filters?.assignee) params.set('assignee', filters.assignee); if (filters?.due) params.set('due', filters.due); const query = params.toString(); return request<TailoringTask[]>(`/api/tailoring/tasks${query ? `?${query}` : ''}`)
  },
  tailoringTask: (taskId: number) => request<TailoringTask>(`/api/tailoring/tasks/${taskId}`),
  updateTailoringTask: (taskId: number, payload: { stage?: TailoringStage; assignee?: string; due_at?: string | null; priority?: 'NORMAL' | 'URGENT'; notes?: string }) => request<TailoringTask>(`/api/tailoring/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  transitionTailoringTask: (taskId: number, stage: TailoringStage) => request<TailoringTransition>(`/api/tailoring/tasks/${taskId}/transition`, { method: 'POST', body: JSON.stringify({ stage }) }),
  tailoringLines: () => request<TailoringTask[]>('/api/tailoring/tasks'),
  updateTailoringStage: (lineId: number, stage: TailoringStage) => request(`/api/order-lines/${lineId}/tailoring-stage`, { method: 'PATCH', body: JSON.stringify({ tailoring_stage: stage }) }),
  integrationChannels: () => request<ChannelConnection[]>('/api/integrations/channels'),
  integrationOutbox: (filters?: { status?: string; event_type?: string }) => { const params = new URLSearchParams(); if (filters?.status) params.set('status', filters.status); if (filters?.event_type) params.set('event_type', filters.event_type); const query = params.toString(); return request<IntegrationOutboxItem[]>(`/api/integrations/outbox${query ? `?${query}` : ''}`) },
  integrationOutboxItem: (id: number) => request<IntegrationOutboxItem>(`/api/integrations/outbox/${id}`),
  retryIntegrationOutboxItem: (id: number) => request<IntegrationOutboxItem>(`/api/integrations/outbox/${id}/retry`, { method: 'POST' }),
}
