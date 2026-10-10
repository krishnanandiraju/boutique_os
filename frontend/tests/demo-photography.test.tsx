import { beforeEach, expect, test, vi } from 'vitest'
import { acceptanceApi, type ProductView } from '../src/acceptanceApi'
import { api } from '../src/api'
import { loadDemoPhotography } from '../src/features/workspace/demoPhotography'
import { demoCustomerPhoto, demoProfileName, loadDemoMeasurements } from '../src/features/workspace/demoCustomers'
vi.mock('../src/acceptanceApi', () => ({ acceptanceApi: { productMedia: vi.fn(), uploadProductImage: vi.fn() } }))
vi.mock('../src/api', () => ({ api: { customers: vi.fn(), customerMeasurementProfiles: vi.fn(), createMeasurementProfile: vi.fn() } }))
const product = { id: 1, name: 'Cotton Kurta - Blue' } as ProductView
beforeEach(() => { vi.resetAllMocks(); vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['png'], { type: 'image/png' }) })); vi.mocked(acceptanceApi.productMedia).mockResolvedValue([]) })
test('loads three matching product views and retries a partial import without duplicates', async () => {
  vi.mocked(acceptanceApi.productMedia).mockResolvedValue([{ original_filename: 'kurta-front.png' }] as Awaited<ReturnType<typeof acceptanceApi.productMedia>>)
  expect(await loadDemoPhotography([product])).toBe(2)
  expect(vi.mocked(acceptanceApi.uploadProductImage).mock.calls.map(([, file]) => file.name)).toEqual(['kurta-alternate.png', 'kurta-detail.png'])
})
test('preserves existing product photography', async () => {
  vi.mocked(acceptanceApi.productMedia).mockResolvedValue([{ original_filename: 'my-shop-photo.jpg' }] as Awaited<ReturnType<typeof acceptanceApi.productMedia>>)
  expect(await loadDemoPhotography([product])).toBe(0)
  expect(acceptanceApi.uploadProductImage).not.toHaveBeenCalled()
})
test('propagates missing asset failures before uploading invalid content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
  await expect(loadDemoPhotography([product])).rejects.toThrow('library could not be loaded')
  expect(acceptanceApi.uploadProductImage).not.toHaveBeenCalled()
})
test('only associates a fictional portrait with exact seeded customer identity', () => {
  expect(demoCustomerPhoto({ name: 'Anjali Rao', phone: 'real-phone' })).toBeUndefined()
  expect(demoCustomerPhoto({ name: 'Anjali Rao', phone: '+91-9000000001' })).toContain('person-01.png')
})
test('labels measurement fixtures as unverified and never replaces existing measurements', async () => {
  vi.mocked(api.customers).mockResolvedValue([{ id: 1, name: 'Anjali Rao', phone: '+91-9000000001', merchant_id: 1, notes: null, email: null }])
  vi.mocked(api.customerMeasurementProfiles).mockResolvedValue([])
  expect(await loadDemoMeasurements()).toBe(1)
  expect(api.createMeasurementProfile).toHaveBeenCalledWith(1, expect.objectContaining({ name: demoProfileName, created_by: 'demo-photo-fixture-unverified', notes: expect.stringContaining('not measured') }))
  vi.mocked(api.customerMeasurementProfiles).mockResolvedValue([{ name: demoProfileName }] as Awaited<ReturnType<typeof api.customerMeasurementProfiles>>)
  expect(await loadDemoMeasurements()).toBe(0)
  expect(api.createMeasurementProfile).toHaveBeenCalledTimes(1)
})
