import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'
const api = axios.create({ baseURL: BASE })

export const getSubjects = (userId = 'default') =>
  api.get('/subjects', { params: { user_id: userId } }).then(r => r.data)

export const createSubject = (name, userId = 'default') =>
  api.post('/subjects', { name, user_id: userId }).then(r => r.data)

export const uploadFile = (subjectId, file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/upload?subject_id=${subjectId}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
  }).then(r => r.data)
}

export const askQuestion = (subjectId, question) =>
  api.post('/ask', { subject_id: subjectId, question }).then(r => r.data)

export const generateStudy = (subjectId, topic = null, mcqCount = 5, shortAnswerCount = 3) =>
  api.post('/study', {
    subject_id: subjectId,
    topic,
    mcq_count: mcqCount,
    short_answer_count: shortAnswerCount,
  }).then(r => r.data)

export const getFileUrl = fileId => `${BASE}/file/${fileId}`
