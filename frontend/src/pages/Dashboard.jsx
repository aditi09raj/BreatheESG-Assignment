import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

const STATUS_COLORS = {
  PENDING:  'bg-yellow-100 text-yellow-800',
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  FLAGGED:  'bg-orange-100 text-orange-800',
}

const SCOPE_COLORS = {
  1: 'bg-blue-100 text-blue-800',
  2: 'bg-purple-100 text-purple-800',
  3: 'bg-indigo-100 text-indigo-800',
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
      {sub && <div className={`text-xs mt-2 font-medium px-2 py-0.5 rounded-full inline-block ${color}`}>{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/dashboard/stats/').then(r => setStats(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400">Loading…</div>
  if (!stats) return <div className="p-8 text-red-500">Failed to load stats</div>

  const { by_status = {}, by_scope = {}, by_source = {}, recent_runs = [], flagged_sample = [] } = stats

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Overview</h1>

      {/* Status breakdown */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Total records" value={stats.total_records} />
        <StatCard label="Pending review" value={by_status.PENDING ?? 0} sub="Needs action" color="bg-yellow-100 text-yellow-800" />
        <StatCard label="Flagged" value={by_status.FLAGGED ?? 0} sub="Suspicious" color="bg-orange-100 text-orange-800" />
        <StatCard label="Approved" value={by_status.APPROVED ?? 0} sub="Locked" color="bg-green-100 text-green-800" />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        {/* By scope */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">By Scope</h2>
          <div className="space-y-3">
            {[1, 2, 3].map(s => (
              <div key={s} className="flex items-center justify-between">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SCOPE_COLORS[s]}`}>
                  Scope {s}
                </span>
                <span className="text-sm font-semibold text-gray-900">{by_scope[s] ?? by_scope[String(s)] ?? 0}</span>
              </div>
            ))}
          </div>
        </div>

        {/* By source */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">By Source</h2>
          <div className="space-y-3">
            {[
              ['SAP_FUEL', 'SAP Fuel & Procurement'],
              ['UTILITY_ELECTRICITY', 'Utility Electricity'],
              ['TRAVEL', 'Corporate Travel'],
            ].map(([key, label]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{label}</span>
                <span className="text-sm font-semibold text-gray-900">{by_source[key] ?? 0}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent ingestion runs */}
      <div className="bg-white rounded-xl border border-gray-200 mb-8">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-700">Recent Ingestion Runs</h2>
          <Link to="/ingest" className="text-xs text-green-600 hover:underline">Upload new →</Link>
        </div>
        <div className="divide-y divide-gray-50">
          {recent_runs.length === 0 && (
            <div className="px-5 py-4 text-sm text-gray-400">No runs yet</div>
          )}
          {recent_runs.map(run => (
            <div key={run.id} className="px-5 py-3 flex items-center justify-between text-sm">
              <div>
                <span className="font-medium text-gray-800">{run.source_name}</span>
                <span className="text-gray-400 ml-2 text-xs">{run.file_name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-gray-500 text-xs">
                  {run.records_parsed}/{run.records_total} parsed
                  {run.records_failed > 0 && <span className="text-red-500 ml-1">{run.records_failed} failed</span>}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  run.status === 'COMPLETED' ? 'bg-green-50 text-green-700'
                  : run.status === 'FAILED' ? 'bg-red-50 text-red-700'
                  : 'bg-yellow-50 text-yellow-700'
                }`}>{run.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Flagged records */}
      {flagged_sample.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-700">Flagged — needs investigation</h2>
            <Link to="/review?status=FLAGGED" className="text-xs text-green-600 hover:underline">View all →</Link>
          </div>
          <div className="divide-y divide-gray-50">
            {flagged_sample.map(rec => (
              <Link key={rec.id} to={`/review/${rec.id}`} className="px-5 py-3 flex items-center justify-between text-sm hover:bg-gray-50">
                <div>
                  <span className="font-medium text-gray-800">{rec.activity_type}</span>
                  <span className="text-gray-500 ml-2">{rec.quantity} {rec.unit}</span>
                  <span className="text-gray-400 ml-2 text-xs">{rec.period_start}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SCOPE_COLORS[rec.scope]}`}>
                  Scope {rec.scope}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
