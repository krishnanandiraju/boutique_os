import { beforeEach, expect, test, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { VirtualTryOn } from '../src/features/workspace/VirtualTryOn'
import { CustomerCrmModal } from '../src/features/workspace/CustomerCrmModal'
import { CatalogWorkspaceV4 } from '../src/features/workspace/CatalogWorkspaceV4'
import { acceptanceApi } from '../src/acceptanceApi'
import type { Customer } from '../src/types'
vi.mock('../src/customerCrmApi', () => ({ customerCrmApi: {profile: vi.fn().mockRejectedValue(new Error('offline')), occasions: vi.fn().mockResolvedValue([])} }))
vi.mock('../src/acceptanceApi', () => ({ absoluteMediaUrl: (p: string) => p, acceptanceApi: {products: vi.fn()} }))
const customer: Customer = {id: 1, merchant_id: 1, name: 'Anjali Rao', phone: '+91-9000000001', email: null, notes: null, photo_url: '/media/1/customers/1/person-01-v2.png'}
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/status') ? {ok: true,json: async () => ({configured: false, design_configured: false})} : {ok: true,blob: async () => new Blob(['photo'], {type: 'image/png'})}))
  vi.mocked(acceptanceApi.products).mockResolvedValue([])
})
test('saved CRM photograph appears automatically in try-on without an import action', async () => {
  render(<MantineProvider><VirtualTryOn customerId={1} customerName={customer.name} savedPhotoUrl={customer.photo_url} garments={[{key:'1:base',itemId:1,name:'Kurta',mediaUrl:'/media/garment.png',fabricOnly:false}]} onBusy={vi.fn()} onNotes={vi.fn()}/></MantineProvider>)
  const image = await screen.findByAltText("Anjali Rao's original photograph", {}, {timeout: 5000})
  await waitFor(() => expect(image.getAttribute('src')).toContain('data:image/png'))
  expect(screen.queryByText(/fictional|unverified|load demo/i)).toBeNull()
})
test('CRM profile shows the photograph associated with its customer', async () => {
  render(<MantineProvider><CustomerCrmModal customer={customer} opened onClose={vi.fn()} onSaved={vi.fn()}/></MantineProvider>)
  expect((await screen.findByAltText(customer.name)).getAttribute('src')).toContain(customer.photo_url)
  expect(screen.queryByText(/fictional|unverified|load demo/i)).toBeNull()
})
test('merchandise no longer has a photo-library or loading button', async () => {
  render(<MantineProvider><CatalogWorkspaceV4/></MantineProvider>)
  await waitFor(() => expect(acceptanceApi.products).toHaveBeenCalled())
  expect(screen.queryByRole('button',{name:/photo library|load demo/i})).toBeNull()
})

test('long kurta previews use full-length garment coverage', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/status') ? {ok: true,json: async () => ({configured: true, provider: 'huggingface', design_configured: false})} : {ok: true,blob: async () => new Blob(['photo'], {type: 'image/png'})}))
  render(<MantineProvider><VirtualTryOn customerId={1} customerName={customer.name} savedPhotoUrl={customer.photo_url} garments={[{key:'1:base',itemId:1,name:'Cotton Kurta - Blue',mediaUrl:'/media/garment.png',fabricOnly:false}]} onBusy={vi.fn()} onNotes={vi.fn()}/></MantineProvider>)
  const input = await screen.findByLabelText('Garment type', {selector: 'input'}) as HTMLInputElement
  expect(input.value).toBe('Long kurta, dress or complete outfit')
})


test('saved merchandise photograph appears automatically and approved photo is optional to replace', () => {
  render(<MantineProvider><VirtualTryOn customerId={1} customerName={customer.name} garments={[{key:'3:base',itemId:3,name:'Cotton Kurta - Blue',mediaUrl:'/media/1/products/3/kurta-front-clean.png',fabricOnly:false}]} onBusy={vi.fn()} onNotes={vi.fn()}/></MantineProvider>)
  expect(screen.getByAltText('Cotton Kurta - Blue').getAttribute('src')).toContain('/media/1/products/3/kurta-front-clean.png')
  expect(screen.getByText('Replace product photo (optional)')).toBeTruthy()
})

test('a variant shows its product reference but still requires an exact photograph', () => {
  render(<MantineProvider><VirtualTryOn customerId={1} customerName={customer.name} garments={[{key:'3:5',itemId:3,variantId:5,name:'Cotton Kurta - Red',mediaUrl:'/media/1/products/3/kurta-front-clean.png',fabricOnly:false}]} onBusy={vi.fn()} onNotes={vi.fn()}/></MantineProvider>)
  expect(screen.getByAltText('Cotton Kurta - Red')).toBeTruthy()
  expect(screen.queryByText('Replace product photo (optional)')).toBeNull()
  expect(screen.getByRole('button', {name:'Preview on me'}).hasAttribute('disabled')).toBe(true)
})


test('repeat catalog previews receive distinct idempotency keys without uploading the garment', async () => {
  const requests: RequestInit[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/status')) return {ok:true,json:async()=>({configured:true})}
    if (url.endsWith('/generate')) { requests.push(init!); return {ok:true,json:async()=>({image:'data:image/png;base64,test'})} }
    return {ok:true,blob:async()=>new Blob(['photo'],{type:'image/png'})}
  }))
  render(<MantineProvider><VirtualTryOn customerId={1} customerName={customer.name} savedPhotoUrl={customer.photo_url} garments={[{key:'3:base',itemId:3,name:'Cotton Kurta - Blue',mediaUrl:'/media/1/products/3/kurta-front-clean.png',fabricOnly:false}]} onBusy={vi.fn()} onNotes={vi.fn()}/></MantineProvider>)
  await screen.findByAltText("Anjali Rao's original photograph", {}, {timeout:5000})
  fireEvent.click(screen.getByRole('checkbox'))
  const button=screen.getByRole('button',{name:'Preview on me'})
  await waitFor(()=>expect(button.hasAttribute('disabled')).toBe(false))
  fireEvent.click(button)
  await screen.findByText('Your look')
  fireEvent.click(button)
  await waitFor(()=>expect(requests).toHaveLength(2))
  const keys=requests.map(r=>(r.headers as Record<string,string>)['Idempotency-Key'])
  expect(keys[0]).toBeTruthy()
  expect(keys[1]).not.toBe(keys[0])
  expect((requests[0].body as FormData).get('category')).toBe('one-pieces')
  expect((requests[0].body as FormData).get('garment_source')).toBe('catalog')
  expect((requests[0].body as FormData).has('garment')).toBe(false)
})
