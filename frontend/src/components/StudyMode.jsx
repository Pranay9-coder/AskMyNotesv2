import { useState } from 'react'
import { generateStudy } from '../services/api'

/**
 * StudyMode — generates MCQs and short-answer items from subject notes.
 * Props: subject (SubjectRead)
 */
export default function StudyMode({ subject }) {
  const [topic, setTopic] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [revealed, setRevealed] = useState({}) // {mcqIndex: true}

  if (!subject) return <p className="text-gray-500 text-sm p-4">Select a subject for Study Mode.</p>

  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    setRevealed({})
    try {
      const data = await generateStudy(subject.id, topic || null)
      setResult(data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="Optional topic focus (e.g. 'photosynthesis')"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          disabled={loading}
        />
        <button
          className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? 'Generating…' : 'Generate Study Set'}
        </button>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {result && (
        <div className="space-y-6">
          {/* MCQs */}
          {result.mcqs?.length > 0 && (
            <section>
              <h3 className="font-semibold text-gray-800 mb-3">Multiple Choice ({result.mcqs.length})</h3>
              <div className="space-y-4">
                {result.mcqs.map((mcq, i) => (
                  <MCQCard
                    key={i}
                    mcq={mcq}
                    revealed={!!revealed[i]}
                    onReveal={() => setRevealed(r => ({ ...r, [i]: true }))}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Short answers */}
          {result.short_answers?.length > 0 && (
            <section>
              <h3 className="font-semibold text-gray-800 mb-3">Short Answers ({result.short_answers.length})</h3>
              <div className="space-y-3">
                {result.short_answers.map((sa, i) => (
                  <SACard key={i} item={sa} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

function MCQCard({ mcq, revealed, onReveal }) {
  const diffColor = { easy: 'bg-green-100 text-green-700', medium: 'bg-yellow-100 text-yellow-700', hard: 'bg-red-100 text-red-700' }

  return (
    <div className="border rounded-xl p-4 bg-white shadow-sm space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-900">{mcq.question}</p>
        <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${diffColor[mcq.difficulty] || 'bg-gray-100'}`}>
          {mcq.difficulty}
        </span>
      </div>
      <ul className="space-y-1">
        {mcq.options.map((opt, j) => (
          <li
            key={j}
            className={`text-sm px-3 py-1 rounded-lg transition-colors
              ${revealed && opt.is_correct ? 'bg-green-100 text-green-800 font-semibold' :
                revealed && !opt.is_correct ? 'text-gray-400' :
                'text-gray-700 hover:bg-gray-50'}`}
          >
            <span className="font-mono mr-2">{opt.label}.</span>{opt.text}
          </li>
        ))}
      </ul>
      {revealed ? (
        <p className="text-xs text-gray-500 border-t pt-2 italic">{mcq.explanation}</p>
      ) : (
        <button
          className="text-xs text-indigo-600 hover:underline"
          onClick={onReveal}
        >
          Show answer
        </button>
      )}
      {mcq.citation && (
        <p className="text-xs text-gray-400">
          Source: {mcq.citation.file} p.{mcq.citation.page_start}
        </p>
      )}
    </div>
  )
}

function SACard({ item }) {
  const [show, setShow] = useState(false)
  return (
    <div className="border rounded-xl p-4 bg-white shadow-sm">
      <p className="text-sm font-medium text-gray-900 mb-2">{item.question}</p>
      {show ? (
        <>
          <p className="text-sm text-gray-700 bg-blue-50 rounded-lg px-3 py-2">{item.answer}</p>
          {item.citation && (
            <p className="text-xs text-gray-400 mt-1">
              Source: {item.citation.file} p.{item.citation.page_start}
            </p>
          )}
        </>
      ) : (
        <button className="text-xs text-indigo-600 hover:underline" onClick={() => setShow(true)}>
          Show answer
        </button>
      )}
    </div>
  )
}
