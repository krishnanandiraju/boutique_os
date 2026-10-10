import { beforeEach, expect, test, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import { acceptanceApi, type ProductView } from '../src/acceptanceApi'
import { ProductGallery } from '../src/features/workspace/ProductGallery'
vi.mock('../src/acceptanceApi', () => ({ absoluteMediaUrl: (path: string) => path, acceptanceApi: { productMedia: vi.fn(), markPrimaryMedia: vi.fn(), uploadProductImage: vi.fn() } }))
const images = [
  { id: 1, item_id: 8, original_filename: 'front.png', mime_type: 'image/png', storage_key: 'front.png', is_primary: true, sort_order: 0 },
  { id: 2, item_id: 8, original_filename: 'detail.png', mime_type: 'image/png', storage_key: 'detail.png', is_primary: false, sort_order: 1 },
]
beforeEach(() => { vi.resetAllMocks(); vi.mocked(acceptanceApi.productMedia).mockResolvedValue(images) })
test('browses alternate photos and persists the selected cover', async () => {
  const changed = vi.fn()
  render(<MantineProvider><ProductGallery product={{id:8,name:'Blue kurta'} as ProductView} onClose={vi.fn()} onChanged={changed}/></MantineProvider>)
  await screen.findByRole('button', { name: 'View image 2 of Blue kurta' })
  await userEvent.click(screen.getByRole('button', { name: 'View image 2 of Blue kurta' }))
  expect(screen.getByAltText('Blue kurta — detail.png').getAttribute('src')).toBe('/media/detail.png')
  await userEvent.click(screen.getByRole('button', { name: 'Use as cover' }))
  await waitFor(() => expect(acceptanceApi.markPrimaryMedia).toHaveBeenCalledWith(8,2,1))
  await waitFor(() => expect(changed).toHaveBeenCalledOnce())
})
test('shows a recoverable error when gallery loading fails', async () => {
  vi.mocked(acceptanceApi.productMedia).mockRejectedValue(new Error('offline'))
  render(<MantineProvider><ProductGallery product={{id:8,name:'Blue kurta'} as ProductView} onClose={vi.fn()} onChanged={vi.fn()}/></MantineProvider>)
  expect((await screen.findByRole('alert')).textContent).toContain('Unable to load product images')
})
