import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'

const STATUS_COLORS = {
  PENDING:  'bg-yellow-100 text-yellow-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
  FLAGGED:  'bg-orange-100 text-orange-700',
}

function Field({ label, value, mono }) {
  return (
    <div>
      <dt className="text-xs text-gray-400 uppercase tracking-wide">{label}</dt>
      <dd className={`text-sm text-gray-800 mt-0.5 ${mono ? 'font-mono' : ''}`}>{value ?? '—'}</dd>
    </div>
  )
}

export default function RecordDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [notes, setNotes] = useState('')
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [editReason, setEditReason] = useState('')
  const [msg, setMsg] = useState('')

  const load = async () => {
    const { data } = await api.get(`/records/${id}/`)
    setRecord(data)
    setEditForm({
      quantity: data.quantity,
      unit: data.unit,
      period_start: data.period_start,
      period_end: data.period_end,
      facility_code: data.facility_code,
      facility_name: data.facility_name,
      country_code: data.country_code,
    })
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  const action = async (act) => {
    setActionLoading(true)
    await api.post(`/records/${id}/review/`, { action: act, notes })
    await load()
    setNotes('')
    setMsg(`Record ${act}d.`)
    setActionLoading(false)
    setTimeout(() => setMsg(''), 3000)
  }

  const saveEdit = async () => {
    setActionLoading(true)
    await api.patch(`/records/${id}/edit/`, { ...editForm, reason: editReason })
    await load()
    setEditMode(false)
    setEditReason('')
    setMsg('Changes saved.')
    setActionLoading(false)
    setTimeout(() => setMsg(''), 3000)
  }

  if (loading) return <div className="p-8 text-gray-400">Loading…</div>
  if (!record) return <div className="p-8 text-red-500">Not found</div>

  const extra = record.extra_data ?? {}

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <button onClick={() => navigate(-1)} className="text-sm text-gray-400 hover:text-gray-600 mb-4">← Back</button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {record.activity_type} — {parseFloat(record.quantity).toLocaleString()} {record.unit}
          </h1>
          <p className="text-sm text-gray-500 mt-1">{record.source_type_display} · {record.ghg_category}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium px-3 py-1 rounded-full ${STATUS_COLORS[record.review_status]}`}>
            {record.review_status_display}
          </span>
          {record.locked_for_audit && (
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">Locked for audit</span>
          )}
        </div>
      </div>

      {msg && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700 mb-4">{msg}</div>
      )}

      {/* Activity data */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="text-sm font-medium text-gray-700 mb-4">Activity data</h2>
        {editMode ? (
          <div className="space-y-3">
            {[
              ['Quantity', 'quantity', 'number'],
              ['Unit', 'unit', 'text'],
              ['Period start', 'period_start', 'date'],
              ['Period end', 'period_end', 'date'],
              ['Facility code', 'facility_code', 'text'],
              ['Facility name', 'facility_name', 'text'],
              ['Country code', 'country_code', 'text'],
            ].map(([label, key, type]) => (
              <div key={key} className="flex gap-3 items-center">
                <label className="w-32 text-xs text-gray-500">{label}</label>
                <input
                  type={type}
                  className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                  value={editForm[key] ?? ''}
                  onChange={e => setEditForm(f => ({ ...f, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div className="flex gap-3 items-center">
              <label className="w-32 text-xs text-gray-500">Reason for edit</label>
              <input
                className="flex-1 border border-gray-300 rounded px-2 py-1 text-sm"
                placeholder="Required — will appear in audit trail"
                value={editReason}
                onChange={e => setEditReason(e.target.value)}
              />
            </div>
            <div className="flex gap-2 mt-2">
              <button onClick={saveEdit} disabled={actionLoading || !editReason}
                className="bg-green-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-40">
                Save changes
              </button>
              <button onClick={() => setEditMode(false)}
                className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <Field label="Scope" value={record.scope_display} />
            <Field label="Activity type" value={record.activity_type} />
            <Field label="GHG category" value={record.ghg_category} />
            <Field label="Quantity" value={`${parseFloat(record.quantity).toLocaleString()} ${record.unit}`} />
            {record.unit !== record.unit_original && (
              <Field label="Original quantity" value={`${parseFloat(record.quantity_original).toLocaleString()} ${record.unit_original}`} />
            )}
            {record.conversion_factor && record.conversion_factor !== '1.0000000000' && (
              <Field label="Conversion factor" value={record.conversion_factor} mono />
            )}
            <Field label="Period start" value={record.period_start} />
            <Field label="Period end" value={record.period_end} />
            <Field label="Facility" value={record.facility_name || record.facility_code} />
            <Field label="Country" value={record.country_code} />
            <Field label="Source ID" value={record.source_id} mono />
          </div>
        )}
        {!record.locked_for_audit && !editMode && (
          <button onClick={() => setEditMode(true)}
            className="mt-4 text-xs text-green-600 hover:underline">
            Edit this record
          </button>
        )}
      </div>

      {/* Source-specific metadata */}
      {Object.keys(extra).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Source metadata</h2>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(extra).filter(([, v]) => v !== null && v !== '').map(([k, v]) => (
              <Field key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
            ))}
          </div>
        </div>
      )}

      {/* Review actions */}
      {!record.locked_for_audit && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Review decision</h2>
          <textarea
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 resize-none"
            rows={2}
            placeholder="Add notes (optional for approve, required to explain flagging)"
            value={notes}
            onChange={e => setNotes(e.target.value)}
          />
          <div className="flex gap-2">
            <button disabled={actionLoading} onClick={() => action('approve')}
              className="bg-green-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-40">
              Approve & lock
            </button>
            <button disabled={actionLoading} onClick={() => action('reject')}
              className="bg-red-500 text-white text-sm px-4 py-2 rounded-lg hover:bg-red-600 disabled:opacity-40">
              Reject
            </button>
            <button disabled={actionLoading} onClick={() => action('flag')}
              className="bg-orange-500 text-white text-sm px-4 py-2 rounded-lg hover:bg-orange-600 disabled:opacity-40">
              Flag for investigation
            </button>
            {record.review_status !== 'PENDING' && (
              <button disabled={actionLoading} onClick={() => action('reset')}
                className="text-sm px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40">
                Reset to pending
              </button>
            )}
          </div>
        </div>
      )}

      {/* Audit trail */}
      {record.edits?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Audit trail (v{record.version})</h2>
          <div className="space-y-3">
            {record.edits.map(e => (
              <div key={e.id} className="text-xs text-gray-600 border-l-2 border-gray-200 pl-3">
                <div className="font-medium text-gray-700">
                  {e.edited_by_name} · {new Date(e.edited_at).toLocaleString()}
                </div>
                <div>
                  <span className="text-gray-500">{e.field_name}</span>
                  {' '}<span className="line-through text-red-400">{e.old_value}</span>
                  {' → '}<span className="text-green-700">{e.new_value}</span>
                </div>
                {e.reason && <div className="text-gray-400 italic mt-0.5">{e.reason}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
