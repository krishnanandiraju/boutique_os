import type { InventoryType, OrderStatus, TailoringStage } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type AudienceSegment = 'WOMEN' | 'MEN' | 'UNISEX' | 'CHILDREN'

export type TenantProfile = {
  id: number
  merchant_id: number
  supported_audiences: AudienceSegment[]
  default_audience: AudienceSegment
  garment_types: string[]
}

export type VariantView = {
  id: number
  name: string
  sku: string | null
  option_values: Record<string, string>
  selling_price: string | null
  cost_price: string | null
  quantity_available: string
}

export type ProductView = {
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
  availability: string
  quantity_available: string
  audience: AudienceSegment | null
  collection: string | null
  season: string | null
  description: string | null
  primary_media_url: string | null
  media_count: number
  variants: VariantView[]
}

export type VariantSeed = {
  name: string
  sku?: string
  option_values: Record<string, string>
  selling_price?: string
  cost_price?: string
  quantity: string
}

export type ProductCreateFull = {
  merchant_id?: number
  name: string
  sku?: string
  inventory_type: InventoryType
  category: string
  fabric?: string
  color?: string
  selling_price: string
  cost_price?: string
  quantity: string
  audience?: AudienceSegment
  collection?: string
  season?: string
  description?: string
  variants: VariantSeed[]
}

export type MediaAsset = {
  id: number
  item_id: number | null
  original_filename: string
  mime_type: string
  storage_key: string
  is_primary: boolean
  sort_order: number
  url?: string | null
}

export type VariantAwareLineCreate = {
  item_id: number
  variant_id?: number
  quantity: string
  requires_tailoring: boolean
  measurement_profile_id?: number
  measurement_version_id?: number
}

export type VariantAwareOrder = {
  id: number
  merchant_id: number
  customer_id: number
  status: OrderStatus
  total_amount: string
  created_at: string
  lines: Array<{
    id: number
    item_id: number
    item_name: string
    variant_id: number | null
    variant_name: string | null
    variant_sku: string | null
    quantity: string
    unit_price: string
    requires_tailoring: boolean
    tailoring_stage: TailoringStage | null
  }>
}

type ErrorPayload = { error?: { message?: string; code?: string }; detail?: string }

async function parseError(response: Response): Promise<Error> {
  try {
    const payload = await response.json() as ErrorPayload
    return new Error(payload.error?.message || payload.detail || payload.error?.code || `Request failed (${response.status})`)
  } catch {
    return new Error(response.statusText || `Request failed (${response.status})`)
  }
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) throw await parseError(response)
  return response.json() as Promise<T>
}

export function absoluteMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export const acceptanceApi = {
  products: () => json<ProductView[]>('/api/catalog/products'),
  product: (itemId: number) => json<ProductView>(`/api/catalog/products/${itemId}`),
  createProduct: (payload: ProductCreateFull) => json<ProductView>('/api/catalog/products', { method: 'POST', body: JSON.stringify(payload) }),
  uploadProductImage: async (itemId: number, file: File): Promise<MediaAsset> => {
    const body = new FormData()
    body.append('file', file)
    const response = await fetch(`${API_BASE_URL}/api/media/upload?item_id=${itemId}`, { method: 'POST', body })
    if (!response.ok) throw await parseError(response)
    return response.json() as Promise<MediaAsset>
  },
  productMedia: (itemId: number) => json<MediaAsset[]>(`/api/items/${itemId}/media`),
  markPrimaryMedia: (itemId: number, mediaId: number, sortOrder = 0) => json<MediaAsset>(`/api/items/${itemId}/media/${mediaId}`, { method: 'PATCH', body: JSON.stringify({ is_primary: true, sort_order: sortOrder }) }),
  tenantProfile: (merchantId = 1) => json<TenantProfile>(`/api/tenants/${merchantId}/profile`),
  saveTenantProfile: (profile: Pick<TenantProfile, 'supported_audiences' | 'default_audience' | 'garment_types'>, merchantId = 1) => json<TenantProfile>(`/api/tenants/${merchantId}/profile`, { method: 'PUT', body: JSON.stringify(profile) }),
  createVariantAwareOrder: (payload: { customer_id: number; lines: VariantAwareLineCreate[] }) => json<VariantAwareOrder>('/api/orders/variant-aware', { method: 'POST', body: JSON.stringify(payload) }),
}
