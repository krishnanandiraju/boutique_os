const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type CustomerMetrics = {
  order_count: number
  total_spend: string
  average_order_value: string
  estimated_gross_margin: string
  last_purchase_at: string | null
}

export type CustomerProfile = {
  id: number
  customer_id: number
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  postal_code: string | null
  country: string
  date_of_birth: string | null
  anniversary_date: string | null
  preferred_language: string | null
  acquisition_source: string | null
  acquisition_detail: string | null
  customer_segment: string | null
  merchant_tags: string[]
  preferences: Record<string, unknown>
  marketing_consent: boolean
  updated_at: string
  metrics: CustomerMetrics
}

export type CustomerProfileSummary = {
  customer_id: number
  customer_segment: string | null
  merchant_tags: string[]
  acquisition_source: string | null
  city: string | null
  anniversary_date: string | null
  order_count: number
  total_spend: string
  average_order_value: string
  last_purchase_at: string | null
  next_event_label: string | null
  next_event_date: string | null
}

export type CustomerOccasion = {
  id: number
  customer_id: number
  occasion_type: 'BIRTHDAY' | 'WEDDING_ANNIVERSARY' | 'FIRST_PURCHASE_ANNIVERSARY' | 'CUSTOM'
  label: string
  event_date: string
  recurring_annually: boolean
  offer_kind: 'PERCENTAGE' | 'FLAT' | 'GIFT' | 'NONE'
  offer_value: string | null
  offer_code: string | null
  lead_days: number
  notes: string | null
  active: boolean
  created_at: string
  next_occurrence: string
  anniversary_number: number | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = await response.json() as { error?: { message?: string }; detail?: string }
      message = payload.error?.message || payload.detail || message
    } catch { /* keep fallback */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const customerCrmApi = {
  summaries: () => request<CustomerProfileSummary[]>('/api/v2/customers/profiles'),
  profile: (customerId: number) => request<CustomerProfile>(`/api/v2/customers/${customerId}/profile`),
  saveProfile: (customerId: number, payload: Omit<CustomerProfile, 'id' | 'customer_id' | 'updated_at' | 'metrics'>) =>
    request<CustomerProfile>(`/api/v2/customers/${customerId}/profile`, { method: 'PUT', body: JSON.stringify(payload) }),
  occasions: (customerId: number) => request<CustomerOccasion[]>(`/api/v2/customers/${customerId}/occasions`),
  addOccasion: (customerId: number, payload: {
    occasion_type: CustomerOccasion['occasion_type']
    label: string
    event_date: string
    recurring_annually: boolean
    offer_kind: CustomerOccasion['offer_kind']
    offer_value?: string
    offer_code?: string
    lead_days: number
    notes?: string
  }) => request<CustomerOccasion>(`/api/v2/customers/${customerId}/occasions`, { method: 'POST', body: JSON.stringify(payload) }),
}
