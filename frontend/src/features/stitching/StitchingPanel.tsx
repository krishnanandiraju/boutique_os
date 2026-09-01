import { useEffect, useMemo, useState } from 'react'
import { stitchingApi } from './api'
import type {
  CustomerFitInsight,
  FeedbackSeverity,
  FitArea,
  FitDirection,
  GarmentTypeDefinition,
  StitchFeedback,
  StitchRecord,
  StitchRecordStatus,
} from './types'

const statuses: StitchRecordStatus[] = ['DRAFT', 'MEASURED', 'CUTTING', 'STITCHING', 'TRIAL', 'ALTERATION', 'READY', 'DELIVERED', 'CLOSED']
const directions: FitDirection[] = ['TOO_LONG', 'TOO_SHORT', 'TOO_TIGHT', 'TOO_LOOSE', 'TOO_DEEP', 'TOO_SHALLOW', 'TOO_HIGH', 'TOO_LOW', 'OTHER']
const severities: FeedbackSeverity[] = ['MINOR', 'MODERATE', 'MAJOR']

function pretty(value: string): string {
  return value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function feedbackSentence(feedback: StitchFeedback): string {
  const adjustment = feedback.adjustment_value ? ` by ${feedback.adjustment_value} ${feedback.adjustment_unit || ''}` : ''
  return `${pretty(feedback.fit_area)} ${pretty(feedback.direction)}${adjustment}`
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
  const openFeedback = records.flatMap((record) => record.feedback).filter((feedback) => !feedback.resolved)

  async function refresh() {
    const [garmentRows, recordRows] = await Promise.all([stitchingApi.garmentTypes(), stitchingApi.customerRecords(customerId)])
    setGarments(garmentRows)
    setRecords(recordRows)
    if (!selectedRecordId && recordRows[0]) setSelectedRecordId(recordRows[0].id)
    if (recordRows.length === 0) setInsight(null)
  }

  useEffect(() => {
    let active = true
    void Promise.all([stitchingApi.garmentTypes(), stitchingApi.customerRecords(customerId)])
      .then(([garmentRows, recordRows]) => {
        if (!active) return
        setGarments(garmentRows)
        setRecords(recordRows)
        setSelectedRecordId(recordRows[0]?.id ?? null)
        if (recordRows.length === 0) setInsight(null)
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : 'Failed to load stitch history'))
    return () => { active = false }
  }, [customerId])

  useEffect(() => {
    if (!selectedRecord) return
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
    setError('')
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

  async function toggleResolved(feedback: StitchFeedback) {
    setBusy(true)
    setError('')
    try {
      await stitchingApi.updateFeedback(feedback.id, { resolved: !feedback.resolved })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update fit feedback')
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

      <div className="fit-memory-summary">
        <article className="fit-summary-card"><span>Stitch records</span><strong>{records.length}</strong><small>Garments with remembered history</small></article>
        <article className="fit-summary-card attention"><span>Open observations</span><strong>{openFeedback.length}</strong><small>Fit notes still relevant</small></article>
        <article className="fit-summary-card insight"><span>Recurring memories</span><strong>{insight?.recurring_feedback.length ?? 0}</strong><small>Patterns worth checking next time</small></article>
      </div>

      <div className="feature-grid two-col">
        <article className="panel-card stitch-create-card">
          <div>
            <p className="eyebrow">New garment</p>
            <h4>Start a stitch record</h4>
          </div>
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

        <article className="panel-card fit-memory-card">
          <div>
            <p className="eyebrow">Learned from history</p>
            <h4>Fit memory for {selectedGarment?.display_name || 'this garment'}</h4>
          </div>
          {insight?.recurring_feedback.length ? (
            <div className="insight-list">
              {insight.recurring_feedback.map((memory) => {
                const [area, issue] = memory.split(':')
                return <div key={memory} className="insight-chip"><strong>{pretty(area)}</strong><span>{pretty(issue)}</span></div>
              })}
            </div>
          ) : <p className="state">Recurring feedback appears after the same fit observation is recorded more than once.</p>}
          <div className="fit-memory-callout">
            <strong>Next-stitch check</strong>
            <p>{insight?.recurring_feedback.length ? 'Review these learned signals with the customer before cutting. Do not silently alter historical measurements.' : 'No recurring adjustment is inferred yet. Keep collecting trial feedback.'}</p>
          </div>
        </article>
      </div>

      {selectedRecord && (
        <div className="feature-grid two-col">
          <article className="panel-card stitch-record-card">
            <div className="section-head">
              <div>
                <p className="eyebrow">Selected stitch</p>
                <h4>{selectedGarment?.display_name || pretty(selectedRecord.garment_type_code)}</h4>
                <p className="state">Record #{selectedRecord.id}{selectedRecord.tailor_name ? ` · ${selectedRecord.tailor_name}` : ''}</p>
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
            {selectedRecord.style_notes && <div className="stitch-note"><span>Style brief</span><p>{selectedRecord.style_notes}</p></div>}
          </article>

          <article className="panel-card trial-feedback-card">
            <div>
              <p className="eyebrow">Trial / alteration</p>
              <h4>Add structured fit feedback</h4>
            </div>
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
            <button type="button" disabled={busy} onClick={() => void saveFeedback()}>Remember this fit feedback</button>
          </article>
        </div>
      )}

      <div className="feedback-history-card">
        <div className="section-head">
          <div><p className="eyebrow">Customer history</p><h4>Fit observations across stitches</h4></div>
          <span className="feedback-count">{records.flatMap((record) => record.feedback).length} observations</span>
        </div>
        <div className="feedback-list">
          {records.flatMap((record) => record.feedback.map((feedback) => (
            <article key={feedback.id} className={feedback.resolved ? 'feedback-row resolved' : 'feedback-row'}>
              <div className={`severity-dot ${feedback.severity.toLowerCase()}`} aria-hidden="true" />
              <div className="feedback-main">
                <div className="feedback-heading">
                  <strong>{feedbackSentence(feedback)}</strong>
                  <span>{pretty(record.garment_type_code)} · Record #{record.id}</span>
                </div>
                {feedback.comment && <p>{feedback.comment}</p>}
                <small>{pretty(feedback.severity)} · {feedback.resolved ? 'Resolved for this stitch' : 'Open fit memory'}</small>
              </div>
              <button type="button" className="secondary-action" disabled={busy} onClick={() => void toggleResolved(feedback)}>{feedback.resolved ? 'Reopen' : 'Mark resolved'}</button>
            </article>
          )))}
          {records.every((record) => record.feedback.length === 0) && <div className="client-empty">No fit feedback yet. Add the first trial observation above.</div>}
        </div>
      </div>
    </section>
  )
}
