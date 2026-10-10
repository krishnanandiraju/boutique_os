import { api } from '../../api'
import type { Customer } from '../../types'
import { demoAssetUrl } from './demoPhotography'
export const demoProfileName = 'DEMO ONLY — unverified photo fixture'
export const demoCustomers = [
  { name: 'Anjali Rao', phone: '+91-9000000001', photo: 'person-01.png', measurements: { bust: 36, waist: 30, hip: 39, shoulder: 14, blouse_length: 15, sleeve_length: 10, armhole: 16, front_neck_depth: 7, back_neck_depth: 9 } },
  { name: 'Priya Sharma', phone: '+91-9000000002', photo: 'person-02.png', measurements: { bust: 42, waist: 36, hip: 45, shoulder: 15, blouse_length: 16, sleeve_length: 10, armhole: 19, front_neck_depth: 7, back_neck_depth: 9 } },
  { name: 'Neha Reddy', phone: '+91-9000000003', photo: 'person-03.png', measurements: { bust: 32, waist: 26, hip: 35, shoulder: 13, blouse_length: 14, sleeve_length: 9, armhole: 15, front_neck_depth: 6, back_neck_depth: 8 } },
]
export function demoCustomerFor(customer: Pick<Customer, 'name' | 'phone'>) {
  return demoCustomers.find((c) => c.name === customer.name && c.phone === customer.phone)
}
export function demoCustomerPhoto(customer: Pick<Customer, 'name' | 'phone'>) {
  const demo = demoCustomerFor(customer)
  return demo ? demoAssetUrl(demo.photo) : undefined
}
export async function loadDemoMeasurements() {
  const customers = await api.customers()
  let added = 0
  for (const fixture of demoCustomers) {
    const customer = customers.find((c) => demoCustomerFor(c) === fixture)
    if (!customer) continue
    const profiles = await api.customerMeasurementProfiles(customer.id)
    if (profiles.some((p) => p.name === demoProfileName)) continue
    await api.createMeasurementProfile(customer.id, { name: demoProfileName, garment_type: 'BLOUSE', unit: 'INCH', measurements: fixture.measurements, notes: 'SYNTHETIC DEMO DATA. Arbitrary sample values, not measured from this AI-generated portrait. Not validated body dimensions; do not use for real tailoring or accuracy claims.', created_by: 'demo-photo-fixture-unverified' })
    added++
  }
  return added
}
