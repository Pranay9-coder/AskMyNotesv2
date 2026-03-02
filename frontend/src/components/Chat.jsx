import { useState, useRef, useEffect } from 'react'
import { askQuestion, getFileUrl } from '../services/api'
import GroundingMeter from './GroundingMeter'
import EvidencePanel from './EvidencePanel'

/**
 * Chat — the main Q&A interface.
 * Props: subject (SubjectRead object)
 */
export default function Chat({ subject }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedResponse, setSelectedResponse] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!subject) return <p className="text-gray-500 text-sm p-4">Select a subject to start asking questions.</p>

  const handleSend = async () => {
    const q = input.trim()
    if (!q) return
    setInput('')
    const userMsg = { role: 'user', text: q }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    try {
      const data = await askQuestion(subject.id, q)
      const isRefusal = typeof data === 'string' || !data.answer
      const assistantMsg = {
        role: 'assistant',
        isRefusal,
        text: isRefusal ? (typeof data === 'string' ? data : 'Not found in your notes.') : data.answer,
        response: isRefusal ? null : data,
      }
      setMessages(prev => [...prev, assistantMsg])
      if (!isRefusal) setSelectedResponse(data)
    } catch (e) {
      setMessages(prev => [...prev, { role: 'error', text: e.message }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full gap-4">
      {/* Chat column */}
      <div className="flex flex-col flex-1 min-w-0">
        <div className="flex-1 overflow-y-auto space-y-3 p-4 bg-gray-50 rounded-xl">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-prose rounded-2xl px-4 py-2 text-sm shadow-sm cursor-pointer
                  ${m.role === 'user' ? 'bg-blue-600 text-white' :
                    m.role === 'error' ? 'bg-red-100 text-red-700' :
                    m.isRefusal ? 'bg-yellow-100 text-yellow-800 border border-yellow-300' :
                    'bg-white text-gray-900 border border-gray-200'}`}
                onClick={() => m.response && setSelectedResponse(m.response)}
              >
                {m.text}
                {m.response && (
                  <div className="mt-2">
                    <GroundingMeter
                      score={m.response.grounding_score}
                      detail={m.response.grounding_detail}
                      confidence={m.response.confidence}
                    />
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border rounded-2xl px-4 py-2 text-sm text-gray-400 animate-pulse">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 mt-2">
          <input
            className="flex-1 border rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder={`Ask about ${subject.name}…`}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={loading}
          />
          <button
            className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            onClick={handleSend}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>

      {/* Evidence panel */}
      {selectedResponse && (
        <div className="w-80 shrink-0">
          <EvidencePanel response={selectedResponse} />
        </div>
      )}
    </div>
  )
}
