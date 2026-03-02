/**
 * GroundingMeter — visual display of the 0-100 grounding score
 * with component breakdown (top similarity, support ratio, evidence overlap).
 *
 * Props: score (int), detail ({ top_similarity, support_ratio, evidence_overlap }), confidence (str)
 */
export default function GroundingMeter({ score, detail, confidence }) {
  const color =
    score >= 75 ? 'bg-green-500' :
    score >= 50 ? 'bg-yellow-400' :
    'bg-red-400'

  const confidenceColor =
    confidence === 'High' ? 'text-green-600' :
    confidence === 'Medium' ? 'text-yellow-600' :
    'text-red-500'

  return (
    <div className="rounded-xl border border-gray-200 p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-700">Grounding Score</span>
        <span className={`text-sm font-bold ${confidenceColor}`}>{confidence}</span>
      </div>

      {/* Main bar */}
      <div className="w-full bg-gray-100 rounded-full h-4 mb-1">
        <div
          className={`${color} h-4 rounded-full transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
      <p className="text-right text-xs text-gray-500 mb-3">{score} / 100</p>

      {/* Component breakdown */}
      {detail && (
        <div className="space-y-1 text-xs text-gray-600 border-t pt-2">
          <BarRow label="Top Similarity" value={detail.top_similarity} max={1} />
          <BarRow label="Support Ratio" value={detail.support_ratio} max={1} />
          <BarRow label="Evidence Overlap" value={detail.evidence_overlap} max={1} />
        </div>
      )}
    </div>
  )
}

function BarRow({ label, value, max }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <span className="w-32 truncate">{label}</span>
      <div className="flex-1 bg-gray-100 rounded h-1.5">
        <div className="bg-blue-400 h-1.5 rounded" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}
