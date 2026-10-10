import { acceptanceApi, type ProductView } from '../../acceptanceApi'
export const demoProducts = [
  { name: 'Cotton Kurta - Blue', key: 'kurta' },
  { name: 'Designer Blouse', key: 'blouse' },
  { name: 'Hand Embroidered Bridal Lehenga', key: 'lehenga' },
  { name: 'Kanjeevaram Saree', key: 'saree' },
  { name: 'Chanderi Fabric Roll', key: 'fabric' },
]
export const demoAssetUrl = (name: string) => `${import.meta.env.BASE_URL}demo-images/${name}`
export async function loadDemoPhotography(products: ProductView[]) {
  let added = 0
  for (const demo of demoProducts) {
    const product = products.find((p) => p.name === demo.name)
    if (!product) continue
    // Check live media, not the possibly stale catalog count. Retry partial imports safely.
    const media = await acceptanceApi.productMedia(product.id)
    const expected = ['front', 'alternate', 'detail'].map((view) => `${demo.key}-${view}.png`)
    if (media.some((m) => !expected.includes(m.original_filename))) continue
    for (const filename of expected) {
      if (media.some((m) => m.original_filename === filename)) continue
      const response = await fetch(demoAssetUrl(filename))
      if (!response.ok) throw new Error('The demo image library could not be loaded.')
      const blob = await response.blob()
      await acceptanceApi.uploadProductImage(product.id, new File([blob], filename, { type: 'image/png' }))
      added++
    }
  }
  return added
}
