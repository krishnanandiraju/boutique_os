import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import { IntegrationsPanel } from './features/integrations/IntegrationsPanel'
import type {
  Customer,
  DashboardData,
  InventoryLot,
  InventoryMovement,
  InventoryMovementType,
  InventoryType,
  Item,
  MeasurementProfile,
  MeasurementProfileDetail,
  Order,
  OrderStatus,
  TailoringStage,
  TailoringTask,
} from './types'
import './index.css'

type NavKey = 'Dashboard' | 'Catalog' | 'Customers' | 'Orders' | 'Tailoring' | 'Integrations'

type GarmentPreset = 'BLOUSE' | 'KURTA' | 'BOTTOM' | 'GENERAL'

type CartLine = {
  item_id: number
  item_name: string
  inventory_type: InventoryType
  quantity: string
  unit_price: string
  requires_tailoring: boolean
  measurement_profile_id?: number
  measurement_version_id?: number
  measurement_summary?: string
}

const navItems: NavKey[] = ['Dashboard', 'Catalog', 'Customers', 'Orders', 'Tailoring', 'Integrations']

const orderStatuses: OrderStatus[] = [
  'DRAFT',
  'CONFIRMED',
  'TAILORING',
  'READY',
  'PACKED',
  'SHIPPED',
  'DELIVERED',
  'CANCELLED',
]

const tailoringStages: TailoringStage[] = [
  'MEASUREMENT_PENDING',
  'CUTTING',
  'STITCHING',
  'QC',
  'TRIAL_SCHEDULED',
  'ALTERATION',
  'READY',
]

const measurementPresets: Record<GarmentPreset, string[]> = {
  BLOUSE: ['bust', 'waist', 'shoulder', 'blouse_length', 'sleeve_length', 'armhole', 'front_neck_depth', 'back_neck_depth'],
  KURTA: ['bust', 'waist', 'hip', 'shoulder', 'kurta_length', 'sleeve_length', 'armhole'],
  BOTTOM: ['waist', 'hip', 'length', 'thigh', 'bottom_opening'],
  GENERAL: [],
}

function formatMoney(value: string | number): string {
  const num = typeof value === 'string' ? Number(value) : value
  return `INR ${num.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function dueClass(dueAt: string | null, stage: TailoringStage): string {
  if (!dueAt) return 'due-none'
  if (stage === 'READY') return 'due-upcoming'
  const now = new Date()
  const due = new Date(dueAt)
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const endToday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
  if (due < now) return 'due-overdue'
  if (due >= startToday && due < endToday) return 'due-today'
  return 'due-upcoming'
}

function App() {
  const [activeNav, setActiveNav] = useState<NavKey>('Dashboard')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [tailoringTasks, setTailoringTasks] = useState<TailoringTask[]>([])
  const [selectedInventoryItemId, setSelectedInventoryItemId] = useState<number | null>(null)
  const [selectedItemLots, setSelectedItemLots] = useState<InventoryLot[]>([])
  const [selectedItemMovements, setSelectedItemMovements] = useState<InventoryMovement[]>([])
  const [lotForm, setLotForm] = useState({ lot_code: '', quantity: '', cost_price: '', received_at: '', notes: '' })
  const [lotAdjustmentForm, setLotAdjustmentForm] = useState({
    lot_id: '',
    adjustment_type: 'ADJUSTMENT_IN' as InventoryMovementType,
    quantity: '',
    reason: '',
    confirm: false,
  })

  const [showAddItem, setShowAddItem] = useState(false)
  const [itemForm, setItemForm] = useState({
    name: '',
    inventory_type: 'UNIQUE' as InventoryType,
    category: '',
    fabric: '',
    color: '',
    selling_price: '',
    quantity: '1',
  })

  const [showAddCustomer, setShowAddCustomer] = useState(false)
  const [customerForm, setCustomerForm] = useState({ name: '', phone: '', email: '', notes: '' })

  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null)
  const [measurementProfiles, setMeasurementProfiles] = useState<MeasurementProfile[]>([])
  const [selectedProfile, setSelectedProfile] = useState<MeasurementProfileDetail | null>(null)
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [profileName, setProfileName] = useState('Self')
  const [profileGarment, setProfileGarment] = useState<GarmentPreset>('BLOUSE')
  const [profileUnit, setProfileUnit] = useState<'INCH' | 'CM'>('INCH')
  const [measurementInputs, setMeasurementInputs] = useState<Record<string, string>>({})

  const [showOrderComposer, setShowOrderComposer] = useState(false)
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [orderCustomerId, setOrderCustomerId] = useState('')
  const [customerSearch, setCustomerSearch] = useState('')
  const [itemSearch, setItemSearch] = useState('')
  const [lineForm, setLineForm] = useState({
    item_id: '',
    quantity: '1',
    requires_tailoring: false,
    measurement_profile_id: '',
  })
  const [cartLines, setCartLines] = useState<CartLine[]>([])

  const [tailoringFilter, setTailoringFilter] = useState<'ALL' | 'OVERDUE' | 'TODAY' | TailoringStage>('ALL')
  const [selectedTask, setSelectedTask] = useState<TailoringTask | null>(null)
  const [taskEdit, setTaskEdit] = useState({ stage: 'MEASUREMENT_PENDING' as TailoringStage, assignee: '', due_at: '', priority: 'NORMAL' as 'NORMAL' | 'URGENT', notes: '' })

  const loadAll = useCallback(async () => {
    try {
      const [dashboardRes, itemsRes, customersRes, ordersRes, tasksRes] = await Promise.all([
        api.dashboard(),
        api.items(),
        api.customers(),
        api.orders(),
        api.tailoringTasks(),
      ])
      setDashboard(dashboardRes)
      setItems(itemsRes)
      setCustomers(customersRes)
      setOrders(ordersRes)
      setTailoringTasks(tasksRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    }
  }, [])

  const loadCustomerProfiles = useCallback(async (customerId: number) => {
    try {
      const profiles = await api.customerMeasurementProfiles(customerId)
      setMeasurementProfiles(profiles)
      if (profiles.length > 0) {
        const detail = await api.measurementProfile(profiles[0].id)
        setSelectedProfile(detail)
      } else {
        setSelectedProfile(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load measurement profiles')
    }
  }, [])

  async function loadTailoringFiltered(value: typeof tailoringFilter) {
    try {
      if (value === 'ALL') {
        setTailoringTasks(await api.tailoringTasks())
      } else if (value === 'OVERDUE') {
        setTailoringTasks(await api.tailoringTasks({ due: 'overdue' }))
      } else if (value === 'TODAY') {
        setTailoringTasks(await api.tailoringTasks({ due: 'today' }))
      } else {
        setTailoringTasks(await api.tailoringTasks({ stage: value }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to filter worklist')
    }
  }

  async function loadItemDetail(itemId: number) {
    const item = itemById.get(itemId)
    if (!item) return

    setSelectedInventoryItemId(itemId)
    setError('')
    setSuccess('')
    try {
      const [lots, movements] = await Promise.all([
        api.itemLots(itemId),
        api.inventoryMovements({ item_id: itemId, limit: 50 }),
      ])
      setSelectedItemLots(lots)
      setSelectedItemMovements(movements)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load item inventory detail')
    }
  }

  async function submitReceiveLot(e: FormEvent) {
    e.preventDefault()
    if (!selectedItem) return

    try {
      await api.receiveLot(selectedItem.id, {
        lot_code: lotForm.lot_code || undefined,
        quantity: lotForm.quantity,
        cost_price: lotForm.cost_price || undefined,
        received_at: lotForm.received_at || undefined,
        notes: lotForm.notes || undefined,
      })
      setSuccess('Stock received successfully')
      setLotForm({ lot_code: '', quantity: '', cost_price: '', received_at: '', notes: '' })
      await loadItemDetail(selectedItem.id)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to receive stock')
    }
  }

  async function submitLotAdjustment(e: FormEvent) {
    e.preventDefault()
    if (!selectedItem || !lotAdjustmentForm.lot_id) {
      setError('Choose a lot to adjust.')
      return
    }
    if (['ADJUSTMENT_OUT', 'DAMAGE', 'GIFT'].includes(lotAdjustmentForm.adjustment_type) && !lotAdjustmentForm.confirm) {
      setError('Confirm destructive adjustment before saving.')
      return
    }
    try {
      await api.adjustLot(Number(lotAdjustmentForm.lot_id), {
        adjustment_type: lotAdjustmentForm.adjustment_type,
        quantity: lotAdjustmentForm.quantity,
        reason: lotAdjustmentForm.reason || undefined,
      })
      setSuccess('Lot adjusted successfully')
      setLotAdjustmentForm({ lot_id: '', adjustment_type: 'ADJUSTMENT_IN', quantity: '', reason: '', confirm: false })
      await loadItemDetail(selectedItem.id)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to adjust stock')
    }
  }

  useEffect(() => {
    let active = true

    void (async () => {
      try {
        const [dashboardRes, itemsRes, customersRes, ordersRes, tasksRes] = await Promise.all([
          api.dashboard(),
          api.items(),
          api.customers(),
          api.orders(),
          api.tailoringTasks(),
        ])

        if (!active) return

        setDashboard(dashboardRes)
        setItems(itemsRes)
        setCustomers(customersRes)
        setOrders(ordersRes)
        setTailoringTasks(tasksRes)
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load data')
      } finally {
        if (active) setLoading(false)
      }
    })()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedCustomerId) return

    let active = true

    void (async () => {
      try {
        const profiles = await api.customerMeasurementProfiles(selectedCustomerId)
        if (!active) return

        setMeasurementProfiles(profiles)
        if (profiles.length > 0) {
          const detail = await api.measurementProfile(profiles[0].id)
          if (active) setSelectedProfile(detail)
        } else {
          setSelectedProfile(null)
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load measurement profiles')
      }
    })()

    return () => {
      active = false
    }
  }, [selectedCustomerId])

  const itemById = new Map<number, Item>()
  items.forEach((item) => itemById.set(item.id, item))

  const selectedItem = selectedInventoryItemId == null ? null : itemById.get(selectedInventoryItemId) ?? null

  const customerById = new Map<number, Customer>()
  customers.forEach((customer) => customerById.set(customer.id, customer))

  const orderableItems = items.filter((item) => {
    if (item.inventory_type === 'UNIQUE') return item.availability === 'AVAILABLE' || item.availability === 'HELD'
    return Number(item.quantity_available) > 0
  })

  const filteredCustomers = (() => {
    const query = customerSearch.trim().toLowerCase()
    if (!query) return customers
    return customers.filter((customer) => customer.name.toLowerCase().includes(query) || customer.phone.includes(query))
  })()

  const filteredItems = (() => {
    const query = itemSearch.trim().toLowerCase()
    if (!query) return orderableItems
    return orderableItems.filter((item) => item.name.toLowerCase().includes(query) || item.category.toLowerCase().includes(query))
  })()

  const selectedLineItem = lineForm.item_id ? itemById.get(Number(lineForm.item_id)) : undefined

  const selectedCustomerProfiles = orderCustomerId && Number(orderCustomerId) === selectedCustomerId ? measurementProfiles : []

  const selectedMeasurementProfile = selectedCustomerProfiles.find((p) => p.id === Number(lineForm.measurement_profile_id)) || null

  const cartTotal = cartLines.reduce((sum, line) => {
    const lineTotal = Number(line.quantity) * Number(line.unit_price)
    return sum + lineTotal
  }, 0)

  const selectedOrder = orders.find((order) => order.id === selectedOrderId) || null

  const selectedCustomer = customers.find((c) => c.id === selectedCustomerId) || null

  const customerOrders = selectedCustomerId ? orders.filter((order) => order.customer_id === selectedCustomerId) : []

  const worklistSummary = (() => {
    const now = new Date()
    const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const endToday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
    return {
      overdue: tailoringTasks.filter((t) => t.due_at && new Date(t.due_at) < now && t.stage !== 'READY').length,
      today: tailoringTasks.filter((t) => t.due_at && new Date(t.due_at) >= startToday && new Date(t.due_at) < endToday).length,
      stitching: tailoringTasks.filter((t) => t.stage === 'STITCHING').length,
      trial: tailoringTasks.filter((t) => t.stage === 'TRIAL_SCHEDULED').length,
      ready: tailoringTasks.filter((t) => t.stage === 'READY').length,
    }
  })()

  async function submitItem(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    try {
      await api.addItem({
        ...itemForm,
        selling_price: itemForm.selling_price,
        quantity: itemForm.inventory_type === 'UNIQUE' ? '1' : itemForm.quantity,
      })
      setShowAddItem(false)
      setItemForm({ name: '', inventory_type: 'UNIQUE', category: '', fabric: '', color: '', selling_price: '', quantity: '1' })
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add item')
    }
  }

  async function submitCustomer(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    try {
      await api.addCustomer(customerForm)
      setShowAddCustomer(false)
      setCustomerForm({ name: '', phone: '', email: '', notes: '' })
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add customer')
    }
  }

  function clearComposer() {
    setOrderCustomerId('')
    setCustomerSearch('')
    setItemSearch('')
    setLineForm({ item_id: '', quantity: '1', requires_tailoring: false, measurement_profile_id: '' })
    setCartLines([])
  }

  function addCartLine() {
    setError('')
    setSuccess('')

    if (!lineForm.item_id) {
      setError('Select an item for the line.')
      return
    }
    if (!selectedLineItem) {
      setError('Selected item is unavailable.')
      return
    }

    if (selectedLineItem.inventory_type === 'UNIQUE' && cartLines.some((line) => line.item_id === selectedLineItem.id)) {
      setError('Duplicate UNIQUE item in cart is not allowed.')
      return
    }

    const normalizedQty =
      selectedLineItem.inventory_type === 'UNIQUE'
        ? '1'
        : selectedLineItem.inventory_type === 'STOCKED'
          ? String(Math.max(1, Math.trunc(Number(lineForm.quantity || '1'))))
          : lineForm.quantity

    const selectedProfile = selectedMeasurementProfile
    const measurementVersion = selectedProfile?.latest_version

    const summary =
      lineForm.requires_tailoring && selectedProfile && measurementVersion
        ? `Using ${selectedProfile.name} / ${selectedProfile.garment_type || 'GENERAL'} / v${measurementVersion.version_number}`
        : lineForm.requires_tailoring
          ? 'Capture later'
          : undefined

    setCartLines((prev) => [
      ...prev,
      {
        item_id: selectedLineItem.id,
        item_name: selectedLineItem.name,
        inventory_type: selectedLineItem.inventory_type,
        quantity: normalizedQty,
        unit_price: selectedLineItem.selling_price,
        requires_tailoring: lineForm.requires_tailoring,
        measurement_profile_id: lineForm.requires_tailoring && selectedProfile ? selectedProfile.id : undefined,
        measurement_version_id: lineForm.requires_tailoring && measurementVersion ? measurementVersion.id : undefined,
        measurement_summary: summary,
      },
    ])

    setLineForm({ item_id: '', quantity: '1', requires_tailoring: false, measurement_profile_id: '' })
    setItemSearch('')
  }

  function removeCartLine(index: number) {
    setCartLines((prev) => prev.filter((_, i) => i !== index))
  }

  async function createCartOrder() {
    setError('')
    setSuccess('')

    if (!orderCustomerId) {
      setError('Select a customer before creating order.')
      return
    }
    if (cartLines.length === 0) {
      setError('Cart is empty.')
      return
    }

    try {
      const created = await api.createOrder({
        customer_id: Number(orderCustomerId),
        lines: cartLines.map((line) => ({
          item_id: line.item_id,
          quantity: line.quantity,
          requires_tailoring: line.requires_tailoring,
          measurement_profile_id: line.measurement_profile_id,
          measurement_version_id: line.measurement_version_id,
        })),
      })
      setSuccess(`Order #${created.id} created successfully`)
      clearComposer()
      setShowOrderComposer(false)
      await loadAll()
      setSelectedOrderId(created.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create order')
    }
  }

  async function holdItem(itemId: number) {
    if (!customers[0]) {
      setError('Create a customer first')
      return
    }
    setError('')
    setSuccess('')
    try {
      await api.holdItem(itemId, customers[0].id, 24)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to place hold')
    }
  }

  async function releaseItemHold(itemId: number) {
    setError('')
    setSuccess('')
    try {
      await api.releaseHold(itemId)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to release hold')
    }
  }

  async function updateStatus(orderId: number, status: OrderStatus) {
    setError('')
    setSuccess('')
    try {
      await api.updateOrderStatus(orderId, status)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update status')
    }
  }

  function setPresetFields(garment: GarmentPreset) {
    const next: Record<string, string> = {}
    measurementPresets[garment].forEach((field) => {
      next[field] = ''
    })
    setMeasurementInputs(next)
  }

  function addGeneralField() {
    const key = `field_${Object.keys(measurementInputs).length + 1}`
    setMeasurementInputs((prev) => ({ ...prev, [key]: '' }))
  }

  async function saveNewProfile() {
    if (!selectedCustomerId) return
    setError('')
    setSuccess('')

    const measurements = Object.fromEntries(
      Object.entries(measurementInputs)
        .filter(([k, v]) => k.trim() && v.trim())
        .map(([k, v]) => [k.trim(), Number(v)]),
    )

    try {
      const created = await api.createMeasurementProfile(selectedCustomerId, {
        name: profileName,
        garment_type: profileGarment,
        unit: profileUnit,
        measurements,
      })
      setSuccess('Measurement profile created')
      setShowProfileForm(false)
      await loadCustomerProfiles(selectedCustomerId)
      setSelectedProfile(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create profile')
    }
  }

  async function saveNewVersion() {
    if (!selectedProfile) return
    const measurements = Object.fromEntries(
      Object.entries(measurementInputs)
        .filter(([k, v]) => k.trim() && v.trim())
        .map(([k, v]) => [k.trim(), Number(v)]),
    )
    try {
      await api.createMeasurementVersion(selectedProfile.id, { measurements })
      const updated = await api.measurementProfile(selectedProfile.id)
      setSelectedProfile(updated)
      if (selectedCustomerId) await loadCustomerProfiles(selectedCustomerId)
      setSuccess('Saved new measurement version')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save version')
    }
  }

  async function chooseProfile(profileId: number) {
    try {
      const detail = await api.measurementProfile(profileId)
      setSelectedProfile(detail)
      const latest = detail.latest_version
      const source = latest?.measurements || {}
      const mapped: Record<string, string> = {}
      Object.entries(source).forEach(([k, v]) => {
        mapped[k] = String(v)
      })
      setMeasurementInputs(mapped)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile detail')
    }
  }

  async function selectTask(task: TailoringTask) {
    try {
      const full = await api.tailoringTask(task.id)
      setSelectedTask(full)
      setTaskEdit({
        stage: full.stage,
        assignee: full.assignee || '',
        due_at: full.due_at ? full.due_at.slice(0, 16) : '',
        priority: full.priority,
        notes: full.notes || '',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load task')
    }
  }

  async function saveTask() {
    if (!selectedTask) return
    try {
      await api.updateTailoringTask(selectedTask.id, {
        stage: taskEdit.stage,
        assignee: taskEdit.assignee || undefined,
        due_at: taskEdit.due_at ? new Date(taskEdit.due_at).toISOString() : null,
        priority: taskEdit.priority,
        notes: taskEdit.notes,
      })
      setSuccess('Tailoring task updated')
      await loadTailoringFiltered(tailoringFilter)
      await loadAll()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task')
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <h1>BoutiqueOS</h1>
        <p>Meera Boutique</p>
        <nav>
          {navItems.map((item) => (
            <button key={item} type="button" className={activeNav === item ? 'nav-btn active' : 'nav-btn'} onClick={() => setActiveNav(item)}>
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="topbar">
          <h2>{activeNav}</h2>
          <button type="button" onClick={() => void loadAll()}>
            Refresh
          </button>
        </header>

        {loading && <p className="state">Loading...</p>}
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}

        {activeNav === 'Dashboard' && dashboard && (
          <section className="cards">
            <article className="card"><p>Available Pieces</p><h3>{dashboard.available_items}</h3></article>
            <article className="card"><p>Held Pieces</p><h3>{dashboard.held_items}</h3></article>
            <article className="card"><p>Pending Orders</p><h3>{dashboard.orders_pending}</h3></article>
            <article className="card"><p>Tailoring Jobs</p><h3>{dashboard.tailoring_pending}</h3></article>
            <article className="card"><p>Low Stock Items</p><h3>{dashboard.low_stock_items}</h3></article>
            <article className="card"><p>Held Unique Pieces</p><h3>{dashboard.held_items}</h3></article>
            <article className="card"><p>Remnant Fabric Rolls</p><h3>{dashboard.remnant_rolls}</h3></article>
            <article className="card wide"><p>Sales Today</p><h3>{formatMoney(dashboard.sales_today)}</h3></article>
          </section>
        )}

        {activeNav === 'Catalog' && (
          <section>
            <div className="toolbar"><button type="button" onClick={() => setShowAddItem(true)}>+ Add Item</button></div>
            <div className="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Category</th><th>Price</th><th>Availability</th><th>Hold Expiry</th><th>Actions</th></tr></thead><tbody>
              {items.map((item) => (
                <tr key={item.id} className={selectedInventoryItemId === item.id ? 'row-active' : ''}>
                  <td><button type="button" className="link-button" onClick={() => void loadItemDetail(item.id)}>{item.name}</button></td><td>{item.inventory_type}</td><td>{item.category}</td><td>{formatMoney(item.selling_price)}</td>
                  <td><span className={`badge ${item.availability.toLowerCase()}`}>{item.availability}</span></td>
                  <td>{formatDate(item.hold_expires_at)}</td>
                  <td className="actions">
                    {item.inventory_type === 'UNIQUE' && item.availability === 'AVAILABLE' && <button type="button" onClick={() => void holdItem(item.id)}>Hold</button>}
                    {item.inventory_type === 'UNIQUE' && item.availability === 'HELD' && <button type="button" onClick={() => void releaseItemHold(item.id)}>Release Hold</button>}
                    {(item.availability === 'AVAILABLE' || item.availability === 'HELD') && <button type="button" onClick={() => { setActiveNav('Orders'); setShowOrderComposer(true); setLineForm((p) => ({ ...p, item_id: String(item.id) })) }}>Create Order</button>}
                  </td>
                </tr>
              ))}
            </tbody></table></div>

            {selectedItem && (
              <section className="panel-soft inventory-detail">
                <div className="section-head">
                  <h3>{selectedItem.name}</h3>
                  <button type="button" onClick={() => setSelectedInventoryItemId(null)}>Close</button>
                </div>

                <div className="cards inventory-summary">
                  <article className="card"><p>Inventory Type</p><h3>{selectedItem.inventory_type}</h3></article>
                  <article className="card"><p>Category</p><h3>{selectedItem.category}</h3></article>
                  <article className="card"><p>Selling Price</p><h3>{formatMoney(selectedItem.selling_price)}</h3></article>
                  <article className="card"><p>Total Available</p><h3>{selectedItem.quantity_available}</h3></article>
                  <article className="card"><p>Held Quantity</p><h3>{selectedItem.inventory_type === 'UNIQUE' && selectedItem.availability === 'HELD' ? '1' : '0'}</h3></article>
                  <article className="card"><p>Sold / Depleted</p><h3>{selectedItem.inventory_type === 'UNIQUE' ? (selectedItem.availability === 'SOLD' ? '1' : '0') : (Number(selectedItem.quantity_available) <= 0 ? '0' : '0')}</h3></article>
                  <article className="card"><p>Remnant</p><h3>{selectedItem.inventory_type === 'YARDAGE' ? selectedItem.quantity_available : '0'}</h3></article>
                </div>

                <div className="inventory-panel-grid">
                  <div className="panel">
                    <h4>Receive Stock</h4>
                    <form onSubmit={submitReceiveLot} className="inventory-form-grid">
                      <label>Lot / Roll Code<input value={lotForm.lot_code} onChange={(e) => setLotForm((p) => ({ ...p, lot_code: e.target.value }))} placeholder="LOT-001" /></label>
                      <label>Quantity<input type={selectedItem.inventory_type === 'YARDAGE' ? 'number' : 'number'} step={selectedItem.inventory_type === 'YARDAGE' ? '0.1' : '1'} min="0" value={lotForm.quantity} onChange={(e) => setLotForm((p) => ({ ...p, quantity: e.target.value }))} placeholder={selectedItem.inventory_type === 'YARDAGE' ? '5.0' : '10'} required /></label>
                      <label>Cost Price<input value={lotForm.cost_price} onChange={(e) => setLotForm((p) => ({ ...p, cost_price: e.target.value }))} placeholder="0.00" /></label>
                      <label>Received Date<input type="datetime-local" value={lotForm.received_at} onChange={(e) => setLotForm((p) => ({ ...p, received_at: e.target.value }))} /></label>
                      <label>Notes<textarea value={lotForm.notes} onChange={(e) => setLotForm((p) => ({ ...p, notes: e.target.value }))} placeholder="Notes" /></label>
                      <button type="submit">{selectedItem.inventory_type === 'YARDAGE' ? 'Receive Roll' : 'Receive Stock'}</button>
                    </form>
                  </div>

                  <div className="panel">
                    <h4>Adjust Stock</h4>
                    <form onSubmit={submitLotAdjustment} className="inventory-form-grid">
                      <label>Lot<select value={lotAdjustmentForm.lot_id} onChange={(e) => setLotAdjustmentForm((p) => ({ ...p, lot_id: e.target.value }))}>
                        <option value="">Select lot</option>
                        {selectedItemLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code || `LOT-${lot.id}`}</option>)}
                      </select></label>
                      <label>Adjustment Type<select value={lotAdjustmentForm.adjustment_type} onChange={(e) => setLotAdjustmentForm((p) => ({ ...p, adjustment_type: e.target.value as InventoryMovementType }))}>
                        <option value="ADJUSTMENT_IN">ADJUSTMENT_IN</option>
                        <option value="ADJUSTMENT_OUT">ADJUSTMENT_OUT</option>
                        <option value="DAMAGE">DAMAGE</option>
                        <option value="GIFT">GIFT</option>
                        <option value="RETURN">RETURN</option>
                      </select></label>
                      <label>Quantity<input type="number" step={selectedItem.inventory_type === 'YARDAGE' ? '0.1' : '1'} min="0" value={lotAdjustmentForm.quantity} onChange={(e) => setLotAdjustmentForm((p) => ({ ...p, quantity: e.target.value }))} required /></label>
                      <label>Reason<input value={lotAdjustmentForm.reason} onChange={(e) => setLotAdjustmentForm((p) => ({ ...p, reason: e.target.value }))} placeholder="Reason" /></label>
                      {['ADJUSTMENT_OUT', 'DAMAGE', 'GIFT'].includes(lotAdjustmentForm.adjustment_type) && (
                        <label className="checkbox-inline confirm-box"><input type="checkbox" checked={lotAdjustmentForm.confirm} onChange={(e) => setLotAdjustmentForm((p) => ({ ...p, confirm: e.target.checked }))} />Confirm destructive adjustment</label>
                      )}
                      <button type="submit">Adjust</button>
                    </form>
                  </div>
                </div>

                <div className="inventory-grid">
                  <div className="panel">
                    <h4>Inventory Lots</h4>
                    <div className="table-wrap"><table><thead><tr><th>Lot / Roll</th><th>Received</th><th>Original</th><th>Remaining</th><th>Unit</th><th>Status</th><th>Cost</th></tr></thead><tbody>
                      {selectedItemLots.map((lot) => (
                        <tr key={lot.id}>
                          <td>{lot.lot_code || `LOT-${lot.id}`}</td>
                          <td>{formatDate(lot.received_at)}</td>
                          <td>{lot.original_quantity}</td>
                          <td>{lot.quantity}</td>
                          <td>{selectedItem.inventory_type === 'YARDAGE' ? 'metres' : 'pieces'}</td>
                          <td><span className={`badge ${lot.status.toLowerCase()}`}>{lot.status}</span></td>
                          <td>{lot.cost_price ? formatMoney(lot.cost_price) : '-'}</td>
                        </tr>
                      ))}
                      {selectedItemLots.length === 0 && <tr><td colSpan={7}>No lots recorded.</td></tr>}
                    </tbody></table></div>
                  </div>

                  <div className="panel">
                    <h4>Inventory History</h4>
                    <div className="table-wrap"><table><thead><tr><th>Date</th><th>Type</th><th>Lot</th><th>Qty</th><th>Reference</th></tr></thead><tbody>
                      {selectedItemMovements.map((movement) => {
                        const value = Number(movement.quantity)
                        const sign = value >= 0 ? '+' : '-'
                        const referenceText = movement.reference_type === 'order' && movement.reference_id ? `Order #${movement.reference_id}` : movement.reason || movement.reference_type || 'System'
                        return (
                          <tr key={movement.id}>
                            <td>{formatDate(movement.created_at)}</td>
                            <td>{movement.movement_type}</td>
                            <td>{selectedItemLots.find((lot) => lot.id === movement.inventory_lot_id)?.lot_code || `LOT-${movement.inventory_lot_id}`}</td>
                            <td className={value >= 0 ? 'qty-positive' : 'qty-negative'}>{sign}{Math.abs(value)} {selectedItem.inventory_type === 'YARDAGE' ? 'm' : 'pcs'}</td>
                            <td>{referenceText}</td>
                          </tr>
                        )
                      })}
                      {selectedItemMovements.length === 0 && <tr><td colSpan={5}>No movement history.</td></tr>}
                    </tbody></table></div>
                  </div>
                </div>
              </section>
            )}
          </section>
        )}

        {activeNav === 'Customers' && (
          <section className="customer-layout">
            <div className="customer-list panel">
              <div className="toolbar"><button type="button" onClick={() => setShowAddCustomer(true)}>+ Add Customer</button></div>
              {customers.map((customer) => (
                <button key={customer.id} type="button" className={selectedCustomerId === customer.id ? 'customer-pill active' : 'customer-pill'} onClick={() => setSelectedCustomerId(customer.id)}>
                  {customer.name}
                </button>
              ))}
            </div>

            <div className="panel">
              {selectedCustomer ? (
                <>
                  <h3>Customer Info</h3>
                  <p><strong>{selectedCustomer.name}</strong> | {selectedCustomer.phone}</p>
                  <p>{selectedCustomer.email || '-'} | {selectedCustomer.notes || '-'}</p>

                  <div className="section-head">
                    <h3>Measurement Book</h3>
                    <button
                      type="button"
                      onClick={() => {
                        setShowProfileForm(true)
                        setProfileName('Self')
                        setProfileGarment('BLOUSE')
                        setProfileUnit('INCH')
                        setPresetFields('BLOUSE')
                      }}
                    >
                      New Profile
                    </button>
                  </div>

                  <div className="measurement-cards">
                    {measurementProfiles.map((profile) => (
                      <article key={profile.id} className="mini-card">
                        <p><strong>{profile.name}</strong></p>
                        <p>{profile.garment_type || 'GENERAL'} | {profile.unit}</p>
                        <p>Version {profile.latest_version?.version_number || '-'}</p>
                        <p>Updated: {formatDate(profile.updated_at)}</p>
                        <button type="button" onClick={() => void chooseProfile(profile.id)}>View</button>
                      </article>
                    ))}
                  </div>

                  {selectedProfile && (
                    <div className="profile-detail panel-soft">
                      <h4>{selectedProfile.name} / {selectedProfile.garment_type || 'GENERAL'} / {selectedProfile.unit}</h4>
                      <div className="measure-grid">
                        {Object.entries(selectedProfile.latest_version?.measurements || {}).map(([k, v]) => (
                          <div key={k} className="measure-row"><span>{k}</span><span>{v} {selectedProfile.unit === 'INCH' ? 'in' : 'cm'}</span></div>
                        ))}
                      </div>
                      <p>Version history: {selectedProfile.versions.map((v) => `v${v.version_number}`).join(', ')}</p>

                      <h4>Edit Measurements (Save New Version)</h4>
                      <div className="measure-form-grid">
                        {Object.entries(measurementInputs).map(([k, v]) => (
                          <label key={k}>{k}<input value={v} onChange={(e) => setMeasurementInputs((p) => ({ ...p, [k]: e.target.value }))} /></label>
                        ))}
                      </div>
                      <button type="button" onClick={() => void saveNewVersion()}>SAVE NEW VERSION</button>
                    </div>
                  )}

                  {showProfileForm && (
                    <div className="panel-soft">
                      <h4>New Measurement Profile</h4>
                      <div className="measure-form-grid">
                        <label>Profile Name<input value={profileName} onChange={(e) => setProfileName(e.target.value)} /></label>
                        <label>Garment Type
                          <select value={profileGarment} onChange={(e) => { const g = e.target.value as GarmentPreset; setProfileGarment(g); if (g !== 'GENERAL') setPresetFields(g); else setMeasurementInputs({}) }}>
                            <option value="BLOUSE">BLOUSE</option><option value="KURTA">KURTA</option><option value="BOTTOM">BOTTOM</option><option value="GENERAL">GENERAL</option>
                          </select>
                        </label>
                        <label>Unit
                          <select value={profileUnit} onChange={(e) => setProfileUnit(e.target.value as 'INCH' | 'CM')}>
                            <option value="INCH">INCH</option><option value="CM">CM</option>
                          </select>
                        </label>
                      </div>
                      <div className="measure-form-grid">
                        {Object.entries(measurementInputs).map(([k, v]) => (
                          <label key={k}>{k}<input value={v} onChange={(e) => setMeasurementInputs((p) => ({ ...p, [k]: e.target.value }))} /></label>
                        ))}
                      </div>
                      {profileGarment === 'GENERAL' && <button type="button" onClick={addGeneralField}>+ Add Field</button>}
                      <button type="button" onClick={() => void saveNewProfile()}>SAVE MEASUREMENTS</button>
                    </div>
                  )}

                  <h3>Purchase History</h3>
                  <div className="table-wrap"><table><thead><tr><th>Order</th><th>Status</th><th>Total</th><th>Date</th></tr></thead><tbody>
                    {customerOrders.map((order) => <tr key={order.id}><td>#{order.id}</td><td>{order.status}</td><td>{formatMoney(order.total_amount)}</td><td>{formatDate(order.created_at)}</td></tr>)}
                  </tbody></table></div>
                </>
              ) : (
                <p>Select a customer.</p>
              )}
            </div>
          </section>
        )}

        {activeNav === 'Orders' && (
          <section>
            <div className="toolbar"><button type="button" onClick={() => setShowOrderComposer((p) => !p)}>+ New Order</button></div>
            {showOrderComposer && (
              <div className="composer">
                <h3>New Order</h3>
                <div className="composer-grid">
                  <div>
                    <label>Customer search</label>
                    <input value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)} placeholder="Search customer" />
                    <select value={orderCustomerId} onChange={(e) => { setOrderCustomerId(e.target.value); const cid = Number(e.target.value); if (cid && cid !== selectedCustomerId) void loadCustomerProfiles(cid) }}>
                      <option value="">Select customer</option>
                      {filteredCustomers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} ({customer.phone})</option>)}
                    </select>
                  </div>
                  <div>
                    <label>Item search</label>
                    <input value={itemSearch} onChange={(e) => setItemSearch(e.target.value)} placeholder="Search item" />
                    <select value={lineForm.item_id} onChange={(e) => setLineForm({ item_id: e.target.value, quantity: '1', requires_tailoring: false, measurement_profile_id: '' })}>
                      <option value="">Select item</option>
                      {filteredItems.map((item) => <option key={item.id} value={item.id}>{item.name} | {item.inventory_type} | Avl {item.quantity_available} | {formatMoney(item.selling_price)}</option>)}
                    </select>
                  </div>
                  <div>
                    <label>Quantity</label>
                    <input
                      value={lineForm.quantity}
                      disabled={selectedLineItem?.inventory_type === 'UNIQUE'}
                      onChange={(e) => setLineForm((prev) => ({ ...prev, quantity: e.target.value }))}
                      placeholder={selectedLineItem?.inventory_type === 'YARDAGE' ? 'Metres (3.5)' : selectedLineItem?.inventory_type === 'UNIQUE' ? '1' : 'Whole number'}
                    />
                    <label className="checkbox-inline"><input type="checkbox" checked={lineForm.requires_tailoring} onChange={(e) => setLineForm((prev) => ({ ...prev, requires_tailoring: e.target.checked }))} />Requires tailoring</label>
                  </div>
                </div>

                {lineForm.requires_tailoring && (
                  <div className="measure-select">
                    <label>Measurement Profile</label>
                    <select value={lineForm.measurement_profile_id} onChange={(e) => setLineForm((p) => ({ ...p, measurement_profile_id: e.target.value }))}>
                      <option value="">None / Capture Later</option>
                      {selectedCustomerProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name} - {profile.garment_type || 'GENERAL'}
                        </option>
                      ))}
                    </select>
                    {selectedMeasurementProfile && selectedMeasurementProfile.latest_version && (
                      <p className="hint">Using {selectedMeasurementProfile.name} / {selectedMeasurementProfile.garment_type || 'GENERAL'} / v{selectedMeasurementProfile.latest_version.version_number}</p>
                    )}
                  </div>
                )}

                <button type="button" onClick={addCartLine}>Add to Order</button>

                <div className="table-wrap cart"><table><thead><tr><th>Item</th><th>Type</th><th>Quantity</th><th>Unit Price</th><th>Line Total</th><th>Tailoring</th><th>Remove</th></tr></thead><tbody>
                  {cartLines.map((line, idx) => (
                    <tr key={`${line.item_id}-${idx}`}>
                      <td>{line.item_name}</td><td>{line.inventory_type}</td><td>{line.quantity}</td><td>{formatMoney(line.unit_price)}</td><td>{formatMoney(Number(line.quantity) * Number(line.unit_price))}</td><td>{line.measurement_summary || (line.requires_tailoring ? 'Yes' : 'No')}</td>
                      <td><button type="button" onClick={() => removeCartLine(idx)}>Remove</button></td>
                    </tr>
                  ))}
                  {cartLines.length === 0 && <tr><td colSpan={7}>No lines added yet.</td></tr>}
                </tbody></table></div>
                <div className="order-total">Order Total: {formatMoney(cartTotal)}</div>
                <button type="button" onClick={() => void createCartOrder()}>CREATE ORDER</button>
              </div>
            )}

            <div className="table-wrap"><table><thead><tr><th>Order #</th><th>Customer</th><th>Amount</th><th>Status</th><th>Created</th><th>Lines</th></tr></thead><tbody>
              {orders.map((order) => (
                <tr key={order.id} className={selectedOrderId === order.id ? 'row-active' : ''} onClick={() => setSelectedOrderId(order.id)}>
                  <td>{order.id}</td><td>{customerById.get(order.customer_id)?.name || order.customer_id}</td><td>{formatMoney(order.total_amount)}</td>
                  <td><select value={order.status} onChange={(e) => void updateStatus(order.id, e.target.value as OrderStatus)}>{orderStatuses.map((s) => <option key={s} value={s}>{s}</option>)}</select></td>
                  <td>{formatDate(order.created_at)}</td><td>{order.lines.length}</td>
                </tr>
              ))}
            </tbody></table></div>

            {selectedOrder && (
              <section className="order-detail">
                <h3>Order Detail</h3>
                <div className="detail-meta">
                  <span>Order ID: {selectedOrder.id}</span>
                  <span>Customer: {customerById.get(selectedOrder.customer_id)?.name || selectedOrder.customer_id}</span>
                  <span>Status: {selectedOrder.status}</span>
                  <span>Created: {formatDate(selectedOrder.created_at)}</span>
                  <span>Total: {formatMoney(selectedOrder.total_amount)}</span>
                </div>
                <div className="table-wrap"><table><thead><tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Total</th><th>Tailoring Status</th><th>Measurements</th><th>Fulfilled From</th></tr></thead><tbody>
                  {selectedOrder.lines.map((line) => (
                    <tr key={line.id}>
                      <td>{line.item_name || itemById.get(line.item_id)?.name || line.item_id}</td>
                      <td>{line.quantity}</td>
                      <td>{formatMoney(line.unit_price)}</td>
                      <td>{formatMoney(line.line_total)}</td>
                      <td>{line.requires_tailoring ? line.tailoring_stage || 'MEASUREMENT_PENDING' : '-'}</td>
                      <td>{line.measurement_profile_name ? `${line.measurement_profile_name} / ${line.measurement_garment_type || 'GENERAL'} / v${line.measurement_version_number}` : '-'}</td>
                      <td>
                        {line.allocations.length > 0 ? (
                          <div className="allocation-list">
                            {line.allocations.map((allocation) => (
                              <div key={allocation.id}>{allocation.lot_code || `LOT-${allocation.inventory_lot_id}`}: {allocation.quantity}</div>
                            ))}
                          </div>
                        ) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody></table></div>
              </section>
            )}
          </section>
        )}

        {activeNav === 'Tailoring' && (
          <section>
            <div className="cards tailoring-cards">
              <article className="card"><p>Overdue</p><h3>{worklistSummary.overdue}</h3></article>
              <article className="card"><p>Due Today</p><h3>{worklistSummary.today}</h3></article>
              <article className="card"><p>In Stitching</p><h3>{worklistSummary.stitching}</h3></article>
              <article className="card"><p>Awaiting Trial</p><h3>{worklistSummary.trial}</h3></article>
              <article className="card"><p>Ready</p><h3>{worklistSummary.ready}</h3></article>
            </div>

            <div className="filter-row">
              <button type="button" onClick={() => { setTailoringFilter('ALL'); void loadTailoringFiltered('ALL') }}>All</button>
              <button type="button" onClick={() => { setTailoringFilter('OVERDUE'); void loadTailoringFiltered('OVERDUE') }}>Overdue</button>
              <button type="button" onClick={() => { setTailoringFilter('TODAY'); void loadTailoringFiltered('TODAY') }}>Today</button>
              {tailoringStages.map((stage) => (
                <button key={stage} type="button" onClick={() => { setTailoringFilter(stage); void loadTailoringFiltered(stage) }}>{stage.replace('_', ' ')}</button>
              ))}
            </div>

            <div className="table-wrap"><table><thead><tr><th>Due</th><th>Order</th><th>Customer</th><th>Item</th><th>Measurements</th><th>Assignee</th><th>Stage</th><th>Priority</th></tr></thead><tbody>
              {tailoringTasks.map((task) => (
                <tr key={task.id} className={selectedTask?.id === task.id ? 'row-active' : ''} onClick={() => void selectTask(task)}>
                  <td><span className={`due-pill ${dueClass(task.due_at, task.stage)}`}>{task.due_at ? formatDate(task.due_at) : 'NO DUE DATE'}</span></td>
                  <td>#{task.order_id}</td>
                  <td>{task.customer_name}</td>
                  <td>{task.item_name}</td>
                  <td>{task.measurement_profile_name ? `${task.measurement_profile_name} v${task.measurement_version_number}` : 'Capture Later'}</td>
                  <td>{task.assignee || '-'}</td>
                  <td><span className="badge available">{task.stage}</span></td>
                  <td>{task.priority}</td>
                </tr>
              ))}
            </tbody></table></div>

            {selectedTask && (
              <section className="panel-soft task-detail">
                <h3>Tailoring Task Detail</h3>
                <p><strong>Customer:</strong> {selectedTask.customer_name}</p>
                <p><strong>Order:</strong> #{selectedTask.order_id}</p>
                <p><strong>Item:</strong> {selectedTask.item_name}</p>
                <p><strong>Measurement profile:</strong> {selectedTask.measurement_profile_name ? `${selectedTask.measurement_profile_name} / v${selectedTask.measurement_version_number}` : 'Capture Later'}</p>
                {selectedTask.measurement_values && (
                  <div className="measure-grid">
                    {Object.entries(selectedTask.measurement_values).map(([k, v]) => (
                      <div key={k} className="measure-row"><span>{k}</span><span>{v} {selectedTask.measurement_unit === 'INCH' ? 'in' : 'cm'}</span></div>
                    ))}
                  </div>
                )}
                <div className="composer-grid">
                  <label>Assignee<input value={taskEdit.assignee} onChange={(e) => setTaskEdit((p) => ({ ...p, assignee: e.target.value }))} /></label>
                  <label>Due<input type="datetime-local" value={taskEdit.due_at} onChange={(e) => setTaskEdit((p) => ({ ...p, due_at: e.target.value }))} /></label>
                  <label>Priority<select value={taskEdit.priority} onChange={(e) => setTaskEdit((p) => ({ ...p, priority: e.target.value as 'NORMAL' | 'URGENT' }))}><option value="NORMAL">NORMAL</option><option value="URGENT">URGENT</option></select></label>
                  <label>Stage<select value={taskEdit.stage} onChange={(e) => setTaskEdit((p) => ({ ...p, stage: e.target.value as TailoringStage }))}>{tailoringStages.map((stage) => <option key={stage} value={stage}>{stage}</option>)}</select></label>
                </div>
                <label>Notes<textarea value={taskEdit.notes} onChange={(e) => setTaskEdit((p) => ({ ...p, notes: e.target.value }))} /></label>
                <button type="button" onClick={() => void saveTask()}>SAVE</button>
              </section>
            )}
          </section>
        )}

        {activeNav === 'Integrations' && <IntegrationsPanel />}
      </main>

      {showAddItem && (
        <dialog open className="modal"><form onSubmit={submitItem} className="modal-form"><h3>Add Item</h3>
          <input value={itemForm.name} onChange={(e) => setItemForm((p) => ({ ...p, name: e.target.value }))} placeholder="Name" required />
          <select value={itemForm.inventory_type} onChange={(e) => setItemForm((p) => ({ ...p, inventory_type: e.target.value as InventoryType }))}><option value="UNIQUE">UNIQUE</option><option value="STOCKED">STOCKED</option><option value="YARDAGE">YARDAGE</option></select>
          <input value={itemForm.category} onChange={(e) => setItemForm((p) => ({ ...p, category: e.target.value }))} placeholder="Category" required />
          <input value={itemForm.fabric} onChange={(e) => setItemForm((p) => ({ ...p, fabric: e.target.value }))} placeholder="Fabric" />
          <input value={itemForm.color} onChange={(e) => setItemForm((p) => ({ ...p, color: e.target.value }))} placeholder="Color" />
          <input value={itemForm.selling_price} onChange={(e) => setItemForm((p) => ({ ...p, selling_price: e.target.value }))} placeholder="Selling price" required />
          {itemForm.inventory_type !== 'UNIQUE' && <input value={itemForm.quantity} onChange={(e) => setItemForm((p) => ({ ...p, quantity: e.target.value }))} placeholder="Quantity" required />}
          <div className="modal-actions"><button type="button" onClick={() => setShowAddItem(false)}>Cancel</button><button type="submit">Save</button></div>
        </form></dialog>
      )}

      {showAddCustomer && (
        <dialog open className="modal"><form onSubmit={submitCustomer} className="modal-form"><h3>Add Customer</h3>
          <input value={customerForm.name} onChange={(e) => setCustomerForm((p) => ({ ...p, name: e.target.value }))} placeholder="Name" required />
          <input value={customerForm.phone} onChange={(e) => setCustomerForm((p) => ({ ...p, phone: e.target.value }))} placeholder="Phone" required />
          <input value={customerForm.email} onChange={(e) => setCustomerForm((p) => ({ ...p, email: e.target.value }))} placeholder="Email" />
          <input value={customerForm.notes} onChange={(e) => setCustomerForm((p) => ({ ...p, notes: e.target.value }))} placeholder="Notes" />
          <div className="modal-actions"><button type="button" onClick={() => setShowAddCustomer(false)}>Cancel</button><button type="submit">Save</button></div>
        </form></dialog>
      )}
    </div>
  )
}

export default App
