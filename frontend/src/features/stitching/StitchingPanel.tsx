import { useEffect, useMemo, useState } from 'react'
import { stitchingApi } from './api'
import type {
  CustomerFitInsight,
  FeedbackSeverity,
  FitArea,
  FitDirection,
  GarmentTypeDefinition,
  StitchRecord,
  StitchRecordStatus,
} from './types'

const statuses: StitchRecordStatus[] = ['DRAFT', 'MEASURED', 'CUTTING', 'STITCHING', 'TRIAL', 'ALTERATION', 'READY', 'DELIVERED', 'CLOSED']
const directions: FitDirection[] = ['TOO_LONG', 'TOO_SHORT', 'TOO_TIGHT', 'TOO_LOOSE', 'TOO_DEEP', 'TOO_SHALLOW', 'TOO_HIGH', 'TOO_LOW', 'OTHER']
const severities: FeedbackSeverity[] = ['MINOR', 'MODERATE', 'MAJOR']

function pretty(value: string): string {
  return value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function StitchingPanel({ customerId, customerName }: { customerId: number; customerName?: string }) {
  const [garments, setGarments] = useState<GarmentTypeDefinition[]>([])
  const [records, setRecords] = useState<StitchRecord[]>([])
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null)
  const [insight, setInsight] = useState<CustomerFitInsight | null>(null)
  const [garmentType, setGarmentType] = useState('BLOUSE')
  const [tailorName, setTailorName] = useState('')
  const [styleNotes, setStyleNotes] = useState('')
  const [fitArea, setFitArea] = useState<FitArea>('SLEEVE')
  const [direction, setDirection] = useState<FitDirection>('TOO_LONG')
  const [severity, setSeverity] = useState<FeedbackSeverity>('MINOR')
  const [adjustmentValue, setAdjustmentValue] = useState('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const selectedRecord = useMemo(() => records.find((record) => record.id === selectedRecordId) || records[0] || null, [records, selectedRecordId])
  const selectedGarment = garments.find((garment) => garment.code === (selectedRecord?.garment_type_code || garmentType))

  async function refresh() {
    const [garmentRows, recordRows] = await Promise.all([stitchingApi.garmentTypes(), stitchingApi.customerRecords(customerId)])
    setGarments(garmentRows)
    setRecords(recordRows)
    if (!selectedRecordId && recordRows[0]) setSelectedRecordId(recordRows[0].id)
  }

  useEffect(() => {
    let active = true
    void Promise.all([stitchingApi.garmentTypes(), stitchingApi.customerRecords(customerId)])
      .then(([garmentRows, recordRows]) => {
        if (!active) return
        setGarments(garmentRows)
        setRecords(recordRows)
        if (recordRows[0]) setSelectedRecordId(recordRows[0].id)
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : 'Failed to load stitch history'))
    return () => { active = false }
  }, [customerId])

  useEffect(() => {
    if (!selectedRecord) {
      setInsight(null)
      return
    }
    let active = true
    void stitchingApi.customerInsights(customerId, selectedRecord.garment_type_code)
      .then((result) => active && setInsight(result))
      .catch(() => active && setInsight(null))
    return () => { active = false }
  }, [customerId, selectedRecord])

  async function createRecord() {
    setBusy(true)
    setError('')
    try {
      const created = await stitchingApi.createRecord({
        merchant_id: 1,
        customer_id: customerId,
        garment_type_code: garmentType,
        tailor_name: tailorName || undefined,
        style_notes: styleNotes || undefined,
      })
      await refresh()
      setSelectedRecordId(created.id)
      setStyleNotes('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create stitch record')
    } finally {
      setBusy(false)
    }
  }

  async function changeStatus(status: StitchRecordStatus) {
    if (!selectedRecord) return
    setBusy(true)
    try {
      await stitchingApi.updateRecord(selectedRecord.id, { status })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update stitch status')
    } finally {
      setBusy(false)
    }
  }

  async function saveFeedback() {
    if (!selectedRecord) return
    setBusy(true)
    setError('')
    try {
      await stitchingApi.addFeedback(selectedRecord.id, {
        fit_area: fitArea,
        direction,
        severity,
        adjustment_value: adjustmentValue || undefined,
        adjustment_unit: adjustmentValue ? 'INCH' : undefined,
        comment: comment || undefined,
      })
      setComment('')
      setAdjustmentValue('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save fit feedback')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="stitching-feature">
      <div className="section-head">
        <div>
          <p className="eyebrow">Fit Memory</p>
          <h3>Stitch history{customerName ? ` · ${customerName}` : ''}</h3>
          <p className="state">Body measurements stay versioned. Trial feedback is remembered separately so the next stitch can improve without rewriting history.</p>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="cards">
        <article className="card">
          <p>Past stitch records</p>
          <h3>{records.length}</h3>
        </article>
        <article className="card">
          <p>Open fit observations</p>
          <h3>{insight?.unresolved_feedback_count ?? 0}</h3>
        </article>
        <article className="card">
          <p>Recurring fit memories</p>
          <h3>{insight?.recurring_feedback.length ?? 0}</h3>
        </article>
      </div>

      <div className="feature-grid two-col">
        <article className="panel-card">
          <h4>Start a stitch record</h4>
          <label>Garment type
            <select value={garmentType} onChange={(event) => setGarmentType(event.target.value)}>
              {garments.map((garment) => <option key={garment.code} value={garment.code}>{garment.display_name}</option>)}
            </select>
          </label>
          <label>Tailor / master
            <input value={tailorName} onChange={(event) => setTailorName(event.target.value)} placeholder="Optional" />
          </label>
          <label>Style notes
            <textarea value={styleNotes} onChange={(event) => setStyleNotes(event.target.value)} placeholder="Princess cut, elbow sleeves, boat neck..." />
          </label>
          <button type="button" disabled={busy} onClick={() => void createRecord()}>Create stitch record</button>
        </article>

        <article className="panel-card">
          <h4>Fit memory</h4>
          {insight?.recurring_feedback.length ? (
            <div className="insight-list">
              {insight.recurring_feedback.map((memory) => {
                const [area, issue] = memory.split(':')
                return <div key={memory} className="insight-chip"><strong>{pretty(area)}</strong> · {pretty(issue)}</div>
              })}
            </div>
          ) : <p className="state">Recurring feedback appears after the same fit observation is recorded more than once.</p>}
          <p className="state">Examples: sleeve too long, neckline too deep, waist too tight, shoulder too loose.</p>
        </article>
      </div>

      {selectedRecord && (
        <div className="feature-grid two-col">
          <article className="panel-card">
            <div className="section-head">
              <div>
                <h4>{selectedGarment?.display_name || pretty(selectedRecord.garment_type_code)}</h4>
                <p className="state">Record #{selectedRecord.id}</p>
              </div>
              <select value={selectedRecord.id} onChange={(event) => setSelectedRecordId(Number(event.target.value))}>
                {records.map((record) => <option key={record.id} value={record.id}>#{record.id} · {pretty(record.garment_type_code)}</option>)}
              </select>
            </div>
            <label>Workflow stage
              <select value={selectedRecord.status} onChange={(event) => void changeStatus(event.target.value as StitchRecordStatus)}>
                {statuses.map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
              </select>
            </label>
            <div className="measurement-tags">
              {selectedGarment?.measurement_fields.map((field) => <span key={field} className="badge">{pretty(field)}</span>)}
            </div>
          </article>

          <article className="panel-card">
            <h4>Add trial feedback</h4>
            <div className="form-grid">
              <label>Area
                <select value={fitArea} onChange={(event) => setFitArea(event.target.value as FitArea)}>
                  {(selectedGarment?.fit_areas || ['OTHER']).map((area) => <option key={area} value={area}>{pretty(area)}</option>)}
                </select>
              </label>
              <label>Observation
                <select value={direction} onChange={(event) => setDirection(event.target.value as FitDirection)}>
                  {directions.map((item) => <option key={item} value={item}>{pretty(item)}</option>)}
                </select>
              </label>
              <label>Severity
                <select value={severity} onChange={(event) => setSeverity(event.target.value as FeedbackSeverity)}>
                  {severities.map((item) => <option key={item} value={item}>{pretty(item)}</option>)}
                </select>
              </label>
              <label>Adjustment (optional, inches)
                <input type="number" step="0.125" value={adjustmentValue} onChange={(event) => setAdjustmentValue(event.target.value)} placeholder="e.g. 0.5" />
              </label>
            </div>
            <label>Comment
              <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Sleeve felt about half an inch too long at trial." />
            </label>
            <button type="button" disabled={busy} onClick={() => void saveFeedback()}>Save fit feedback</button>
          </article>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Garment</th><th>Stage</th><th>Area</th><th>Feedback</th><th>Severity</th><th>Adjustment</th></tr></thead>
          <tbody>
            {records.flatMap((record) => record.feedback.map((feedback) => (
              <tr key={feedback.id}>
                <td>{pretty(record.garment_type_code)}</td>
                <td>{pretty(record.status)}</td>
                <td>{pretty(feedback.fit_area)}</td>
                <td>{pretty(feedback.direction)}{feedback.comment ? ` · ${feedback.comment}` : ''}</td>
                <td>{pretty(feedback.severity)}</td>
                <td>{feedback.adjustment_value ? `${feedback.adjustment_value} ${feedback.adjustment_unit || ''}` : '-'}</td>
              </tr>
            )))}
            {records.every((record) => record.feedback.length === 0) && <tr><td colSpan={6}>No fit feedback yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}
