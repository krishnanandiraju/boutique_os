import type {
  CustomerFitInsight,
  FitArea,
  FitDirection,
  GarmentTypeDefinition,
  FeedbackSeverity,
  StitchFeedback,
  StitchRecord,
  StitchRecordStatus,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

type ApiErrorPayload = { error?: { message?: string; code?: string } }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as ApiErrorPayload
      message = payload.error?.message || payload.error?.code || message
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const stitchingApi = {
  garmentTypes: () => request<GarmentTypeDefinition[]>('/api/stitching/garment-types'),
  customerRecords: (customerId: number) => request<StitchRecord[]>(`/api/stitching/customers/${customerId}/records`),
  customerInsights: (customerId: number, garmentType: string) =>
    request<CustomerFitInsight>(`/api/stitching/customers/${customerId}/fit-insights/${encodeURIComponent(garmentType)}`),
  createRecord: (payload: {
    merchant_id: number
    customer_id: number
    garment_type_code: string
    order_line_id?: number
    measurement_profile_id?: number
    measurement_version_id?: number
    tailor_name?: string
    style_notes?: string
  }) => request<StitchRecord>('/api/stitching/records', { method: 'POST', body: JSON.stringify(payload) }),
  updateRecord: (recordId: number, payload: { status?: StitchRecordStatus; tailor_name?: string; style_notes?: string; fit_notes?: string }) =>
    request<StitchRecord>(`/api/stitching/records/${recordId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  addFeedback: (recordId: number, payload: {
    fit_area: FitArea
    direction: FitDirection
    severity: FeedbackSeverity
    adjustment_value?: string
    adjustment_unit?: string
    comment?: string
  }) => request<StitchFeedback>(`/api/stitching/records/${recordId}/feedback`, { method: 'POST', body: JSON.stringify(payload) }),
  updateFeedback: (feedbackId: number, payload: { resolved?: boolean; comment?: string; severity?: FeedbackSeverity }) =>
    request<StitchFeedback>(`/api/stitching/feedback/${feedbackId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
}
