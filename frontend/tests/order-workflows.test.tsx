import { beforeEach, expect, test, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { GuidedOrdersWorkspaceV4 } from '../src/features/workspace/GuidedOrdersWorkspaceV4'
import { OrderHistory } from '../src/features/workspace/OrderHistory'
import { acceptanceApi, type ProductView } from '../src/acceptanceApi'
import { domainV2Api, type DiscountRule, type OrderPricing } from '../src/domainV2Api'
import { api } from '../src/api'
import type { Customer, Order } from '../src/types'

vi.mock('../src/acceptanceApi', () => ({ acceptanceApi: { products: vi.fn(), createVariantAwareOrder: vi.fn() } }))
vi.mock('../src/api', () => ({ api: { customerMeasurementProfiles: vi.fn(), updateOrderStatus: vi.fn() } }))
vi.mock('../src/domainV2Api', () => ({ domainV2Api: {
  orderPricing: vi.fn(), discountRules: vi.fn(), applyDiscount: vi.fn(), reverseDiscount: vi.fn(),
} }))

const customer: Customer = { id: 3, merchant_id: 1, name: 'Test customer', phone: '9000000000', email: null, notes: null }
const product: ProductView = {
  id: 8, merchant_id: 1, name: 'Cotton fabric', sku: 'COT-8', inventory_type: 'YARDAGE',
  category: 'Fabric', fabric: 'Cotton', color: null, selling_price: '400.00', cost_price: null,
  published: true, availability: 'AVAILABLE', quantity_available: '10.00', audience: 'UNISEX',
  collection: null, season: null, description: null, primary_media_url: null, media_count: 0, variants: [],
}
const order: Order = {
  id: 11, merchant_id: 1, customer_id: customer.id, status: 'CONFIRMED', total_amount: '1000.00',
  created_at: '2026-09-26T09:00:00Z', lines: [{
    id: 21, item_id: product.id, item_name: product.name, inventory_lot_id: null,
    measurement_profile_id: null, measurement_version_id: null, measurement_profile_name: null,
    measurement_garment_type: null, measurement_unit: null, measurement_values: null, measurement_version_number: null,
    allocations: [], quantity: '2.5', unit_price: '400.00', line_total: '1000.00', requires_tailoring: false, tailoring_stage: null,
  }],
}
const basePricing: OrderPricing = { order_id: 11, subtotal: '1000.00', discount_total: '0.00', total: '1000.00', adjustments: [] }
const discount: DiscountRule = {
  id: 4, merchant_id: 1, name: 'Loyalty', kind: 'PERCENTAGE', scope: 'ORDER', value: '10',
  max_amount: null, requires_reason: true, approval_above_value: null, stackable: true, active: true,
  created_at: '2026-09-26T09:00:00Z',
}
const discounted: OrderPricing = { ...basePricing, discount_total: '100.00', total: '900.00', adjustments: [{
  id: 31, rule_id: 4, order_line_id: null, kind: 'PERCENTAGE', value: '10', amount: '100.00',
  reason: 'Returning customer', source: 'RULE', active: true, created_at: '2026-09-26T09:00:00Z',
}] }

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(acceptanceApi.products).mockResolvedValue([product])
  vi.mocked(api.customerMeasurementProfiles).mockResolvedValue([])
  vi.mocked(domainV2Api.orderPricing).mockResolvedValue(basePricing)
  vi.mocked(domainV2Api.discountRules).mockResolvedValue([discount])
})

test('a customer can order fractional fabric and retain the tailoring selection', async () => {
  const user = userEvent.setup()
  const saved = vi.fn()
  vi.mocked(acceptanceApi.createVariantAwareOrder).mockResolvedValue(order)
  render(<MantineProvider env="test"><GuidedOrdersWorkspaceV4 customers={[customer]} orders={[]} onCreated={saved}/></MantineProvider>)
  await user.click(screen.getByRole('textbox', { name: /Customer/ }))
  await user.click(screen.getByRole('button', { name: /Test customer/ }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('textbox', { name: 'Add product' }))
  await user.click(await screen.findByRole('button', { name: /Cotton fabric/ }))
  const quantity = screen.getByRole('textbox', { name: 'Quantity for Cotton fabric' })
  await user.clear(quantity)
  await user.type(quantity, '2.5')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: 'Continue to customization' }))
  await user.click(screen.getByRole('checkbox', { name: 'Requires tailoring' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByText('Qty 2.5 · Tailoring')).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Confirm order' }))
  await screen.findByText('Order #11 created.')
  expect(acceptanceApi.createVariantAwareOrder).toHaveBeenCalledExactlyOnceWith({
    customer_id: 3, lines: [{ item_id: 8, variant_id: undefined, quantity: '2.5', requires_tailoring: true,
      measurement_profile_id: undefined, measurement_version_id: undefined }],
  })
  expect(saved).toHaveBeenCalledTimes(1)
})

test('a rejected discount keeps its reason, retry updates the total, and delivery follows the saved status', async () => {
  const user = userEvent.setup()
  const changed = vi.fn()
  vi.mocked(domainV2Api.applyDiscount).mockRejectedValueOnce(new Error('Pricing changed; try again.')).mockResolvedValueOnce(discounted)
  vi.mocked(domainV2Api.reverseDiscount).mockResolvedValue({ ...basePricing, adjustments: [
    { ...discounted.adjustments[0], active: false },
    { ...discounted.adjustments[0], id: 32, amount: '-100.00', source: 'REVERSAL:31', active: false, reason: 'Entered by mistake' },
  ] })
  vi.mocked(api.updateOrderStatus).mockResolvedValueOnce({ ...order, status: 'READY' }).mockResolvedValueOnce({ ...order, status: 'DELIVERED' })
  render(<MantineProvider env="test"><OrderHistory orders={[order]} customers={[customer]} onChanged={changed}/></MantineProvider>)
  await user.click(screen.getByRole('button', { name: 'View order #11' }))
  await user.click(await screen.findByRole('combobox', { name: 'Discount rule' }))
  await user.click(screen.getByRole('option', { name: /Loyalty/ }))
  const reason = screen.getByRole('textbox', { name: 'Reason for discount or reversal' })
  await user.type(reason, 'Returning customer')
  await user.click(screen.getByRole('button', { name: 'Apply discount' }))
  await screen.findByText('Pricing changed; try again.')
  expect((reason as HTMLInputElement).value).toBe('Returning customer')
  expect(changed).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Apply discount' }))
  await screen.findByText('Discount applied.')
  expect(screen.getAllByText('₹900.00').length).toBeGreaterThan(0)
  await user.type(reason, 'Entered by mistake')
  await user.click(screen.getByRole('button', { name: 'Reverse #31' }))
  await screen.findByText('Discount reversed; the history is preserved.')
  expect(domainV2Api.reverseDiscount).toHaveBeenCalledExactlyOnceWith(11, 31, 'Entered by mistake')
  expect(screen.queryByRole('button', { name: 'Reverse #31' })).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Mark ready' }))
  await user.click(await screen.findByRole('button', { name: 'Mark delivered' }))
  await screen.findByText('Delivered. Pricing is locked.')
  expect(api.updateOrderStatus).toHaveBeenNthCalledWith(1, 11, 'READY')
  expect(api.updateOrderStatus).toHaveBeenNthCalledWith(2, 11, 'DELIVERED')
  expect(screen.queryByRole('button', { name: 'Apply discount' })).toBeNull()
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(4))
})

test('unfinished tailoring cannot be marked ready in the order screen', async () => {
  const user = userEvent.setup()
  render(<MantineProvider env="test"><OrderHistory orders={[{ ...order, status: 'TAILORING', lines: [
    { ...order.lines[0], requires_tailoring: true, tailoring_stage: 'STITCHING' },
  ] }]} customers={[customer]} onChanged={vi.fn()}/></MantineProvider>)
  await user.click(screen.getByRole('button', { name: 'View order #11' }))
  await screen.findByText('Subtotal')
  const ready = screen.getByRole('button', { name: 'Mark ready' })
  expect((ready as HTMLButtonElement).disabled).toBe(true)
  await user.click(ready)
  expect(api.updateOrderStatus).not.toHaveBeenCalled()
})
