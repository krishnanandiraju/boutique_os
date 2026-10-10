import { expect, test } from 'vitest'
import { customerPhotoUrl } from '../src/features/workspace/demoCustomers'
test('uses the photograph stored against the customer record', () => {
  expect(customerPhotoUrl({photo_url: '/media/1/customers/3/person.png'})).toContain('/media/1/customers/3/person.png')
  expect(customerPhotoUrl({photo_url: null})).toBeUndefined()
  expect(customerPhotoUrl({photo_url: 'https://unrelated.example/person.png'})).toBeUndefined()
})
