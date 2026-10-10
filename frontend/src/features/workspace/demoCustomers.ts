import type { Customer } from '../../types'
const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export function customerPhotoUrl(customer: Pick<Customer, 'photo_url'>) {
  const url = customer.photo_url
  return url?.startsWith('/media/') ? `${base}${url}` : undefined
}
