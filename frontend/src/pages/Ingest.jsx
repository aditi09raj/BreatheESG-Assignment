import { useState, useEffect } from 'react'
import api from '../api/client'

const SOURCE_LABELS = {
  SAP_FUEL: 'SAP Fuel & Procurement',
  UTILITY_ELECTRICITY: 'Utility Electricity',
  TRAVEL: 'Corporate Travel (Concur/Navan)',
}

const SOURCE_HINTS = {
  SAP_FUEL: 'Tab-delimited MB51 export. German locale dates (DD.MM.YYYY) and decimals (1.250,500). Movement types 201/261.',
  UTILITY_ELECTRICITY: 'Billing summary CSV with columns: Account Number, Meter ID, Facility, Bill Start Date, Bill End Date, kWh Usage.',
  TRAVEL: 'Concur Standard Accounting Extract CSV. Handles Airfare, Hotel, Car Rental, Train. Personal expenses are automatically skipped.',
}

export default function Ingest() {
  const [sources, setSources] = useState([])
  const [selectedSource, setSelectedSource] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [runs, setRuns] = useState([])

  useEffect(() => {
    api.get('/sources/').then(r => {
      const d = r.data.results ?? r.data
      setSources(Array.isArray(d) ? d : [])
    }).catch(() => {})
    api.get('/runs/').then(r => {
      const d = r.data.results ?? r.data
      setRuns(Array.isArray(d) ? d : [])
    }).catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!selectedSource || !file) return
    setLoading(true)
    setError('')
    setResult(null)
    const fd = new FormData()
    fd.append('source_id', selectedSource)
    fd.append('file', file)
    try {
      const { data } = await api.post('/ingest/', fd)
      setResult(data)
      const r = await api.get('/runs/')
      setRuns(r.data.results ?? r.data)
    } catch (err) {
      setError(err.response?.data?.error ?? 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const selectedType = sources.find(s => String(s.id) === selectedSource)?.source_type

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Ingest Data</h1>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
        <form onSubmit={submit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Data source</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              value={selectedSource}
              onChange={e => setSelectedSource(e.target.value)}
            >
              <option value="">— select a source —</option>
              {sources.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {selectedType && (
              <p className="text-xs text-gray-500 mt-1.5">{SOURCE_HINTS[selectedType]}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
            <input
              type="file"
              accept=".csv,.txt,.tsv"
              className="w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
              onChange={e => setFile(e.target.files[0])}
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>
          )}

          {result && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
              <strong>Ingestion complete.</strong> {result.records_parsed} records parsed
              {result.records_failed > 0 && `, ${result.records_failed} failed/skipped`}.
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !selectedSource || !file}
            className="bg-green-600 hover:bg-green-700 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            {loading ? 'Processing…' : 'Upload & ingest'}
          </button>
        </form>
      </div>

      {/* Ingestion history */}
      <h2 className="text-sm font-medium text-gray-700 mb-3">Ingestion history</h2>
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-50">
        {runs.length === 0 && (
          <div className="px-5 py-4 text-sm text-gray-400">No runs yet</div>
        )}
        {runs.map(run => (
          <div key={run.id} className="px-5 py-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-medium text-gray-800">{run.source_name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                run.status === 'COMPLETED' ? 'bg-green-50 text-green-700'
                : run.status === 'FAILED' ? 'bg-red-50 text-red-700'
                : 'bg-yellow-50 text-yellow-700'
              }`}>{run.status}</span>
            </div>
            <div className="text-gray-400 text-xs mt-0.5 flex gap-3">
              <span>{run.file_name}</span>
              <span>{run.records_parsed}/{run.records_total} parsed</span>
              {run.records_failed > 0 && <span className="text-red-500">{run.records_failed} failed</span>}
            </div>
            {run.error_summary?.length > 0 && (
              <div className="mt-1 text-xs text-red-600">
                {run.error_summary.slice(0, 2).map((e, i) => (
                  <div key={i}>Row {e.row}: {e.errors?.join(', ')}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
