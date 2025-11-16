async function handle<T>(promise: Promise<Response>): Promise<T> {
  const res = await promise
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return (await res.json()) as T
  try { return (await res.json()) as T } catch { return (undefined as unknown) as T }
}

export const api = {
  listProjects: () => handle<any[]>(fetch('/api/projects/')),
  createProject: (data: { name: string; description?: string }) =>
    handle<any>(fetch('/api/projects/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })),
  uploadData: (projectId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return handle<any>(fetch(`/api/projects/${projectId}/upload-data`, { method: 'POST', body: fd }))
  },
  uploadOntology: (projectId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return handle<any>(fetch(`/api/projects/${projectId}/upload-ontology`, { method: 'POST', body: fd }))
  },
  previewData: (projectId: string, limit = 10) => handle<any>(fetch(`/api/projects/${projectId}/data-preview?limit=${limit}`)),
  analyzeOntology: (projectId: string) => handle<any>(fetch(`/api/projects/${projectId}/ontology-analysis`)),
  generateMappings: (projectId: string, params?: { use_semantic?: boolean; min_confidence?: number }) => {
    const qs = new URLSearchParams()
    if (params?.use_semantic !== undefined) qs.set('use_semantic', String(params.use_semantic))
    if (params?.min_confidence !== undefined) qs.set('min_confidence', String(params.min_confidence))
    return handle<any>(fetch(`/api/mappings/${projectId}/generate?${qs.toString()}`, { method: 'POST' }))
  },
  convertSync: (projectId: string, params?: { output_format?: string; validate?: boolean }) => {
    const qs = new URLSearchParams()
    if (params?.output_format) qs.set('output_format', params.output_format)
    if (params?.validate !== undefined) qs.set('validate', String(params.validate))
    return handle<any>(fetch(`/api/conversion/${projectId}?${qs.toString()}`, { method: 'POST' }))
  },
  convertAsync: (projectId: string, params?: { output_format?: string; validate?: boolean }) => {
    const qs = new URLSearchParams()
    qs.set('use_background', 'true')
    if (params?.output_format) qs.set('output_format', params.output_format)
    if (params?.validate !== undefined) qs.set('validate', String(params.validate))
    return handle<any>(fetch(`/api/conversion/${projectId}?${qs.toString()}`, { method: 'POST' }))
  },
  jobStatus: (taskId: string) => handle<any>(fetch(`/api/conversion/job/${taskId}`)),
  downloadRdf: (projectId: string) => fetch(`/api/conversion/${projectId}/download`),
  fetchMappingYaml: (projectId: string) => fetch(`/api/mappings/${projectId}?raw=true`).then(r => r.text()),
}
