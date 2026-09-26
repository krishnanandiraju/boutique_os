const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) }, ...init })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message = payload?.error?.message || payload?.detail || response.statusText || 'Request failed'
    throw new Error(typeof message === 'string' ? message : 'Request failed')
  }
  return response.json() as Promise<T>
}

export type MeasurementEditMode = 'UNTIL_STAGE' | 'TIME_WINDOW' | 'STAGE_AND_TIME' | 'APPROVAL_AFTER_STAGE'

export type MerchantPolicy = {
  id: number
  merchant_id: number
  measurement_edit_mode: MeasurementEditMode
  measurement_grace_hours: number | null
  measurement_lock_stage: string
  post_lock_requires_approval: boolean
  dashboard_config: Record<string, unknown>
  updated_at: string
}

export type DiscountRule = {
  id: number
  merchant_id: number
  name: string
  kind: 'PERCENTAGE' | 'FLAT'
  scope: 'LINE' | 'ORDER'
  value: string
  max_amount: string | null
  requires_reason: boolean
  approval_above_value: string | null
  stackable: boolean
  active: boolean
  created_at: string
}

export type Supplier = {
  id: number
  merchant_id: number
  name: string
  phone?: string | null
  email?: string | null
  notes?: string | null
  active: boolean
  created_at: string
}

export const domainV2Api = {
  orderPricing: (id:number) => request<OrderPricing>(`/api/v2/orders/${id}/pricing`),
  applyDiscount: (id:number,payload:{rule_id:number;order_line_id?:number;reason:string}) => request<OrderPricing>(`/api/v2/orders/${id}/discounts`,{method:'POST',body:JSON.stringify(payload)}),
  reverseDiscount: (id:number,adjustmentId:number,reason:string) => request<OrderPricing>(`/api/v2/orders/${id}/discounts/${adjustmentId}/reverse`,{method:'POST',body:JSON.stringify({reason})}),
  merchantPolicy: () => request<MerchantPolicy>('/api/v2/merchant-policy'),
  saveMerchantPolicy: (payload: Omit<MerchantPolicy, 'id' | 'merchant_id' | 'updated_at'>) => request<MerchantPolicy>('/api/v2/merchant-policy', { method: 'PUT', body: JSON.stringify(payload) }),
  discountRules: () => request<DiscountRule[]>('/api/v2/discount-rules'),
  createDiscountRule: (payload: { name: string; kind: 'PERCENTAGE' | 'FLAT'; scope: 'LINE' | 'ORDER'; value: string; max_amount?: string; requires_reason: boolean; approval_above_value?: string; stackable: boolean }) => request<DiscountRule>('/api/v2/discount-rules', { method: 'POST', body: JSON.stringify(payload) }),
  suppliers: () => request<Supplier[]>('/api/v2/suppliers'),
  createSupplier: (payload: { name: string; phone?: string; email?: string; notes?: string }) => request<Supplier>('/api/v2/suppliers', { method: 'POST', body: JSON.stringify(payload) }),
}

export type OrderPricing = {order_id:number;subtotal:string;discount_total:string;total:string;adjustments:{id:number;rule_id:number|null;order_line_id:number|null;kind:string;value:string;amount:string;reason:string|null;source:string;active:boolean;created_at:string}[]}
