import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../api/client'

const STATUS_COLORS = {
  PENDING:  'bg-yellow-100 text-yellow-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
  FLAGGED:  'bg-orange-100 text-orange-700',
}
const SCOPE_COLORS = {
  1: 'bg-blue-100 text-blue-700',
  2: 'bg-purple-100 text-purple-700',
  3: 'bg-indigo-100 text-indigo-700',
}

export default function Review() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [records, setRecords] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [bulkNotes, setBulkNotes] = useState('')
  const [bulkLoading, setBulkLoading] = useState(false)
  const [page, setPage] = useState(1)

  const statusFilter = searchParams.get('status') || ''
  const scopeFilter = searchParams.get('scope') || ''
  const sourceFilter = searchParams.get('source_type') || ''

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setLoadError(false)
      const params = new URLSearchParams({ page })
      if (statusFilter) params.set('status', statusFilter)
      if (scopeFilter) params.set('scope', scopeFilter)
      if (sourceFilter) params.set('source_type', sourceFilter)
      const { data } = await api.get(`/records/?${params}`)
      const rows = Array.isArray(data.results ?? data) ? (data.results ?? data) : []
      setRecords(rows)
      setTotal(data.count ?? rows.length)
      setSelected(new Set())
    } catch {
      setRecords([])
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, scopeFilter, sourceFilter, page])

  useEffect(() => { load() }, [load])

  const bulkAction = async (action) => {
    if (selected.size === 0) return
    setBulkLoading(true)
    try {
      await api.post('/records/bulk/', { ids: [...selected], action, notes: bulkNotes })
      setBulkNotes('')
      await load()
    } catch {
      // load() has its own error handling; nothing else to do
    } finally {
      setBulkLoading(false)
    }
  }

  const toggleAll = () => {
    if (selected.size === records.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(records.filter(r => !r.locked_for_audit).map(r => r.id)))
    }
  }

  const setFilter = (key, value) => {
    const p = new URLSearchParams(searchParams)
    if (value) p.set(key, value)
    else p.delete(key)
    p.delete('page')
    setPage(1)
    setSearchParams(p)
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-xl font-semibold text-gray-900 mb-5">Review Queue</h1>

      {/* Filters */}
      <div className="flex gap-3 mb-5 flex-wrap">
        <select
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
          value={statusFilter}
          onChange={e => setFilter('status', e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="FLAGGED">Flagged</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
        </select>
        <select
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
          value={scopeFilter}
          onChange={e => setFilter('scope', e.target.value)}
        >
          <option value="">All scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>
        <select
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
          value={sourceFilter}
          onChange={e => setFilter('source_type', e.target.value)}
        >
          <option value="">All sources</option>
          <option value="SAP_FUEL">SAP Fuel</option>
          <option value="UTILITY_ELECTRICITY">Utility</option>
          <option value="TRAVEL">Travel</option>
        </select>
        <span className="text-sm text-gray-400 self-center ml-auto">{total} records</span>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 flex items-center gap-3 flex-wrap">
          <span className="text-sm text-blue-700 font-medium">{selected.size} selected</span>
          <input
            className="flex-1 min-w-40 border border-blue-200 rounded px-2 py-1 text-sm placeholder:text-blue-300"
            placeholder="Optional notes for this action…"
            value={bulkNotes}
            onChange={e => setBulkNotes(e.target.value)}
          />
          <button disabled={bulkLoading} onClick={() => bulkAction('approve')}
            className="bg-green-600 text-white text-sm px-3 py-1 rounded-lg hover:bg-green-700 disabled:opacity-50">
            Approve all
          </button>
          <button disabled={bulkLoading} onClick={() => bulkAction('reject')}
            className="bg-red-500 text-white text-sm px-3 py-1 rounded-lg hover:bg-red-600 disabled:opacity-50">
            Reject all
          </button>
          <button disabled={bulkLoading} onClick={() => bulkAction('flag')}
            className="bg-orange-500 text-white text-sm px-3 py-1 rounded-lg hover:bg-orange-600 disabled:opacity-50">
            Flag all
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="w-8 px-4 py-3">
                <input type="checkbox"
                  checked={selected.size === records.filter(r => !r.locked_for_audit).length && records.length > 0}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Scope</th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Activity</th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Quantity</th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Period</th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Facility</th>
              <th className="px-4 py-3 text-left font-medium text-gray-500 text-xs uppercase tracking-wide">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-gray-400">Loading…</td></tr>
            )}
            {!loading && loadError && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-red-500">Failed to load records — please refresh or sign in again</td></tr>
            )}
            {!loading && !loadError && records.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-gray-400">No records match the current filters</td></tr>
            )}
            {records.map(rec => (
              <tr key={rec.id} className={`hover:bg-gray-50 ${selected.has(rec.id) ? 'bg-blue-50' : ''}`}>
                <td className="px-4 py-3">
                  {!rec.locked_for_audit && (
                    <input type="checkbox"
                      checked={selected.has(rec.id)}
                      onChange={e => setSelected(s => {
                        const n = new Set(s)
                        e.target.checked ? n.add(rec.id) : n.delete(rec.id)
                        return n
                      })}
                    />
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SCOPE_COLORS[rec.scope]}`}>
                    S{rec.scope}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{rec.activity_type}</div>
                  <div className="text-xs text-gray-400">{rec.source_type_display}</div>
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {parseFloat(rec.quantity).toLocaleString()} {rec.unit}
                  {rec.unit !== rec.unit_original && (
                    <div className="text-xs text-gray-400">
                      was {parseFloat(rec.quantity_original).toLocaleString()} {rec.unit_original}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">
                  {rec.period_start}
                  {rec.period_end !== rec.period_start && <> — {rec.period_end}</>}
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">
                  {rec.facility_name || rec.facility_code || '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[rec.review_status]}`}>
                    {rec.review_status_display}
                  </span>
                  {rec.locked_for_audit && (
                    <span className="ml-1 text-xs text-gray-400">🔒</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Link to={`/review/${rec.id}`} className="text-xs text-green-600 hover:underline">View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex justify-between items-center mt-4 text-sm text-gray-500">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40">← Prev</button>
          <span>Page {page}</span>
          <button disabled={records.length < 50} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40">Next →</button>
        </div>
      )}
    </div>
  )
}
