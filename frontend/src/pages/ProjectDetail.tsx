import React, { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Box, Typography, Button, Stack, Divider, LinearProgress, Alert, Paper, Chip } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const projectId = id as string
  const qc = useQueryClient()

  const [jobId, setJobId] = useState<string | null>(null)
  const [jobResult, setJobResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const preview = useQuery({
    queryKey: ['preview', projectId],
    queryFn: () => api.previewData(projectId, 5),
    enabled: !!projectId,
    retry: false,
  })

  const uploadData = useMutation({
    mutationFn: async () => {
      const input = document.getElementById('data-file') as HTMLInputElement
      if (!input?.files?.[0]) throw new Error('Select a data file')
      return api.uploadData(projectId, input.files[0])
    },
    onSuccess: () => {
      setSuccess('Data file uploaded successfully!')
      setError(null)
      preview.refetch()
    },
    onError: (err: any) => {
      setError('Upload failed: ' + err.message)
      setSuccess(null)
    },
  })

  const uploadOntology = useMutation({
    mutationFn: async () => {
      const input = document.getElementById('ont-file') as HTMLInputElement
      if (!input?.files?.[0]) throw new Error('Select an ontology file')
      return api.uploadOntology(projectId, input.files[0])
    },
    onSuccess: () => {
      setSuccess('Ontology file uploaded successfully!')
      setError(null)
    },
    onError: (err: any) => {
      setError('Upload failed: ' + err.message)
      setSuccess(null)
    },
  })

  const mappingYamlQuery = useQuery({
    queryKey: ['mapping-yaml', projectId],
    queryFn: () => api.fetchMappingYaml(projectId),
    enabled: false,
  })

  const generate = useMutation({
    mutationFn: () => api.generateMappings(projectId, { use_semantic: true, min_confidence: 0.5 }),
    onSuccess: (data) => {
      console.log('Mappings generated:', data)
      const summaryStats = data.mapping_summary?.statistics || {}
      const reportStats = data.alignment_report?.statistics || {}
      const stats = (summaryStats.mapped_columns ? summaryStats : reportStats)
      setSuccess(`Mappings generated! ${stats.mapped_columns || 0}/${stats.total_columns || 0} columns mapped (${stats.mapping_rate ? stats.mapping_rate.toFixed(1) : 0}% ).`)
      setError(null)
      setMappingInfo({ stats, sheets: data.mapping_summary?.sheets || [], raw: data.mapping_config })
      mappingYamlQuery.refetch()
    },
    onError: (err: any) => {
      setError('Mapping generation failed: ' + err.message)
      setSuccess(null)
    },
  })

  const convertSync = useMutation({
    mutationFn: () => api.convertSync(projectId, { output_format: 'turtle', validate: false }),
    onSuccess: (data) => {
      console.log('Conversion complete:', data)
      setSuccess(`✅ RDF generated! ${data.triple_count} triples created.`)
      setError(null)
    },
    onError: (err: any) => {
      setError('Conversion failed: ' + err.message)
      setSuccess(null)
    },
  })

  const convertAsync = useMutation({
    mutationFn: async () => {
      const res = await api.convertAsync(projectId, { output_format: 'turtle', validate: false })
      setJobId(res.task_id)
      setJobResult(null)
      setError(null)
      setSuccess('Conversion job queued! Polling status...')
      return res
    },
    onError: (err: any) => {
      setError('Failed to queue job: ' + err.message)
      setSuccess(null)
    },
  })

  // Poll job status
  React.useEffect(() => {
    if (!jobId) return
    const t = setInterval(async () => {
      try {
        const res = await api.jobStatus(jobId)
        console.log('Job status:', res)
        if (res.status === 'SUCCESS') {
          clearInterval(t)
          setJobResult(res)
          setSuccess(`✅ Background job complete! ${res.result?.triple_count || '?'} triples created.`)
        } else if (res.status === 'FAILURE') {
          clearInterval(t)
          setJobResult(res)
          setError('Background job failed: ' + (res.error || 'Unknown error'))
        }
      } catch (e: any) {
        clearInterval(t)
        setError('Failed to check job status: ' + e.message)
      }
    }, 1500)
    return () => clearInterval(t)
  }, [jobId])

  const [mappingInfo, setMappingInfo] = useState<{stats:any; sheets:any[]}|null>(null)

  const download = async () => {
    try {
      const res = await api.downloadRdf(projectId)
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(text || `Download failed (${res.status})`)
      }
      const cd = res.headers.get('content-disposition') || ''
      const filenameMatch = cd.match(/filename="?([^";]+)"?/)
      const filename = filenameMatch ? filenameMatch[1] : `project-${projectId}-output.ttl`
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      setSuccess(`File downloaded: ${filename}`)
    } catch (err: any) {
      setError('Download failed: ' + err.message)
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Project Detail
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Stack spacing={3}>
        {/* Step 1: Upload Files */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Step 1: Upload Files
          </Typography>
          <Stack spacing={2}>
            <Box>
              <input type="file" id="data-file" accept=".csv,.parquet,.json" />
              <Button
                variant="outlined"
                onClick={() => uploadData.mutate()}
                disabled={uploadData.isPending}
                sx={{ ml: 2 }}
              >
                {uploadData.isPending ? 'Uploading...' : 'Upload Data'}
              </Button>
            </Box>
            <Box>
              <input type="file" id="ont-file" accept=".ttl,.rdf,.owl" />
              <Button
                variant="outlined"
                onClick={() => uploadOntology.mutate()}
                disabled={uploadOntology.isPending}
                sx={{ ml: 2 }}
              >
                {uploadOntology.isPending ? 'Uploading...' : 'Upload Ontology'}
              </Button>
            </Box>
            {(uploadData.isPending || uploadOntology.isPending) && <LinearProgress />}
          </Stack>
        </Paper>

        {/* Step 2: Generate Mappings */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Step 2: Generate Mappings (AI-Powered)
          </Typography>
          <Button
            variant="contained"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            size="large"
          >
            {generate.isPending ? 'Generating with BERT...' : 'Generate Mappings'}
          </Button>
          {generate.isPending && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                AI semantic matching in progress... This may take a few seconds.
              </Typography>
            </Box>
          )}
        </Paper>

        {/* Step 3: Convert to RDF */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Step 3: Convert to RDF
          </Typography>
          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <Button
              variant="contained"
              color="secondary"
              onClick={() => convertSync.mutate()}
              disabled={convertSync.isPending}
            >
              {convertSync.isPending ? 'Converting...' : 'Convert (Sync)'}
            </Button>
            <Button
              variant="outlined"
              onClick={() => convertAsync.mutate()}
              disabled={convertAsync.isPending}
            >
              {convertAsync.isPending ? 'Queueing...' : 'Convert (Background)'}
            </Button>
          </Stack>

          {(convertSync.isPending || convertAsync.isPending) && <LinearProgress />}

          {jobId && !jobResult && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Job ID: {jobId} - Polling status every 1.5 seconds...
            </Alert>
          )}

          {convertSync.data?.triple_count && (
            <Alert severity="success" sx={{ mt: 2 }}>
              ✅ Sync conversion complete: <strong>{convertSync.data.triple_count} triples</strong>
            </Alert>
          )}
        </Paper>

        {/* Step 4: Download */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Step 4: Download RDF Output
          </Typography>
          <Button variant="contained" color="success" onClick={download}>
            Download RDF File
          </Button>
        </Paper>

        {/* Data Preview */}
        {preview.data?.rows && preview.data.rows.length > 0 && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Data Preview ({preview.data.showing} rows)
            </Typography>
            <Box sx={{ maxHeight: 300, overflow: 'auto', bgcolor: '#f5f5f5', p: 2, borderRadius: 1 }}>
              <pre style={{ margin: 0, fontSize: '12px' }}>
                {JSON.stringify(preview.data.rows, null, 2)}
              </pre>
            </Box>
          </Paper>
        )}

        {/* After Generate: Mapping Summary */}
        {mappingInfo && (
          <Paper sx={{ p:3 }}>
            <Typography variant="h6" gutterBottom>Mapping Summary</Typography>
            <Typography variant="body2" sx={{ mb:1 }}>
              Columns mapped: {mappingInfo.stats.mapped_columns}/{mappingInfo.stats.total_columns} ({mappingInfo.stats.mapping_rate?.toFixed(1)}%)
            </Typography>
            {mappingInfo.sheets.map(s => (
              <Box key={s.sheet} sx={{ mb:1 }}>
                <Chip label={s.sheet || 'Sheet'} size="small" sx={{ mr:1 }} />
                <Typography variant="caption">Mapped {s.mapped_columns}/{s.total_columns}: {s.mapped_column_names?.join(', ') || 'None'}</Typography>
              </Box>
            ))}
          </Paper>
        )}

        {mappingYamlQuery.data && (
          <Paper sx={{ p:3 }}>
            <Typography variant="h6" gutterBottom>Mapping YAML</Typography>
            <Box sx={{ maxHeight: 300, overflow: 'auto', fontSize: '12px', bgcolor:'#111', color:'#eee', p:2, borderRadius:1 }}>
              <pre style={{ margin:0 }}>{mappingYamlQuery.data}</pre>
            </Box>
          </Paper>
        )}
      </Stack>
    </Box>
  )
}
