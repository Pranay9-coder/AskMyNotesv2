import { useState } from 'react'
import useSubject from './hooks/useSubject'
import FileUpload from './components/FileUpload'
import Chat from './components/Chat'
import StudyMode from './components/StudyMode'

const TABS = ['Chat', 'Study Mode']

export default function App() {
  const { subjects, selected, setSelected, addSubject, loading, MAX_SUBJECTS } = useSubject()
  const [activeTab, setActiveTab] = useState('Chat')
  const [newSubjectName, setNewSubjectName] = useState('')
  const [subjectError, setSubjectError] = useState('')

  const handleAddSubject = async () => {
    const name = newSubjectName.trim()
    if (!name) return
    try {
      await addSubject(name)
      setNewSubjectName('')
      setSubjectError('')
    } catch (e) {
      setSubjectError(e.message)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between shadow-sm">
        <h1 className="text-xl font-bold text-blue-700 tracking-tight">AskMyNotes</h1>
        <span className="text-xs text-gray-400">Answers only from your notes</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r p-4 flex flex-col gap-4 overflow-y-auto shrink-0">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
              Subjects ({subjects.length}/{MAX_SUBJECTS})
            </p>
            <ul className="space-y-1">
              {subjects.map(s => (
                <li key={s.id}>
                  <button
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
                      ${selected?.id === s.id ? 'bg-blue-100 text-blue-800 font-medium' : 'hover:bg-gray-100 text-gray-700'}`}
                    onClick={() => setSelected(s)}
                  >
                    {s.name}
                  </button>
                </li>
              ))}
            </ul>

            {subjects.length < MAX_SUBJECTS && (
              <div className="mt-3 flex gap-1">
                <input
                  className="flex-1 border rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                  placeholder="New subject…"
                  value={newSubjectName}
                  onChange={e => setNewSubjectName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddSubject()}
                />
                <button
                  className="text-xs bg-blue-600 text-white px-2 py-1 rounded-lg hover:bg-blue-700"
                  onClick={handleAddSubject}
                >
                  +
                </button>
              </div>
            )}
            {subjectError && <p className="text-xs text-red-500 mt-1">{subjectError}</p>}
          </div>

          {/* Upload */}
          {selected && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Upload Notes</p>
              <FileUpload subjectId={selected?.id} />
            </div>
          )}
        </aside>

        {/* Main area */}
        <main className="flex-1 flex flex-col overflow-hidden p-4">
          {/* Tabs */}
          <div className="flex gap-1 mb-4 border-b pb-2">
            {TABS.map(tab => (
              <button
                key={tab}
                className={`px-4 py-1.5 rounded-t-lg text-sm font-medium transition-colors
                  ${activeTab === tab ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-hidden">
            {activeTab === 'Chat' && <Chat subject={selected} />}
            {activeTab === 'Study Mode' && <StudyMode subject={selected} />}
          </div>
        </main>
      </div>
    </div>
  )
}
