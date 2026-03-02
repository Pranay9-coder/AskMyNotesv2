import { useState } from 'react'
import { uploadFile } from '../services/api'

/**
 * FileUpload — drag-and-drop / click upload with progress bar.
 * Props: subjectId, onSuccess()
 */
export default function FileUpload({ subjectId, onSuccess }) {
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState(null) // null | 'uploading' | 'done' | 'error'
  const [message, setMessage] = useState('')

  if (!subjectId) return <p className="text-sm text-gray-500">Select a subject first.</p>

  const handleFile = async (file) => {
    if (!file) return
    setStatus('uploading')
    setProgress(0)
    try {
      const result = await uploadFile(subjectId, file, setProgress)
      setStatus('done')
      setMessage(`Uploaded: ${result.original_name} — ${result.chunk_count} chunks across ${result.page_count} pages`)
      onSuccess && onSuccess(result)
    } catch (e) {
      setStatus('error')
      setMessage(e.response?.data?.detail || e.message)
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
        ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
      onClick={() => document.getElementById('file-input').click()}
    >
      <input
        id="file-input"
        type="file"
        accept=".pdf,.txt"
        className="hidden"
        onChange={(e) => handleFile(e.target.files[0])}
      />
      {status === 'uploading' ? (
        <div>
          <p className="text-sm text-blue-600 mb-2">Uploading… {progress}%</p>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          {status === 'done' ? '✓ ' : ''}
          {status === 'error' ? '✗ ' : ''}
          {message || 'Drop a PDF or TXT file here, or click to browse.'}
        </p>
      )}
    </div>
  )
}
