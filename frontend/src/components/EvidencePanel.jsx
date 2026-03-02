import { getFileUrl } from '../services/api'

/**
 * EvidencePanel — shows citations and evidence snippets for a response.
 * Clicking a citation opens the source file with the page anchor.
 *
 * Props: response (AskResponse object)
 */
export default function EvidencePanel({ response }) {
  if (!response) return null

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-4 space-y-4 overflow-y-auto max-h-full">
      <h3 className="font-semibold text-gray-800 text-sm">Evidence</h3>

      {/* Evidence snippets */}
      {response.evidence_snippets?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase mb-1">Snippets</p>
          <ul className="space-y-2">
            {response.evidence_snippets.map((s, i) => (
              <li key={i} className="text-xs bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2 text-gray-700 italic">
                "{s}"
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Citations */}
      {response.citations?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase mb-1">Citations</p>
          <ul className="space-y-2">
            {response.citations.map((c, i) => (
              <li key={i} className="text-xs border rounded-lg px-3 py-2 bg-gray-50">
                <a
                  href={getFileUrl(c.chunk_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline font-medium"
                >
                  {c.file}
                </a>
                <span className="text-gray-500">
                  {' '}p.{c.page_start}{c.page_start !== c.page_end ? `–${c.page_end}` : ''}
                </span>
                <span className="ml-2 text-gray-400">score: {(c.score * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
