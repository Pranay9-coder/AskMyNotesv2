import { useState, useEffect } from 'react'
import { getSubjects, createSubject } from '../services/api'

/**
 * Manages the list of subjects and the currently selected subject.
 * Enforces MAX_SUBJECTS (3) on the UI side as well.
 */
export default function useSubject() {
  const [subjects, setSubjects] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const MAX_SUBJECTS = 3

  const refresh = async () => {
    setLoading(true)
    try {
      const data = await getSubjects()
      setSubjects(data)
      if (!selected && data.length > 0) setSelected(data[0])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const addSubject = async (name) => {
    if (subjects.length >= MAX_SUBJECTS) {
      throw new Error(`Maximum of ${MAX_SUBJECTS} subjects allowed.`)
    }
    const s = await createSubject(name)
    await refresh()
    setSelected(s)
    return s
  }

  return { subjects, selected, setSelected, addSubject, loading, error, MAX_SUBJECTS }
}
