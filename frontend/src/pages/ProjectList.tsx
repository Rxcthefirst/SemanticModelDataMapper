import React, { useState } from 'react'
import { Typography, Button, Box, Dialog, DialogTitle, DialogContent, TextField, DialogActions, List, ListItemButton, ListItemText, Alert, CircularProgress } from '@mui/material'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'

export default function ProjectList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: projects, isLoading, refetch, error: queryError } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      console.log('🔄 Fetching projects from /api/projects/')
      const result = await api.listProjects()
      console.log('✅ Projects API response:', result)
      console.log('   Type:', typeof result, 'IsArray:', Array.isArray(result), 'Length:', result?.length)
      return result
    },
  })

  // Debug: Log whenever projects data changes
  React.useEffect(() => {
    console.log('📊 Projects state updated:', {
      isLoading,
      hasData: !!projects,
      isArray: Array.isArray(projects),
      length: projects?.length,
      data: projects
    })
  }, [projects, isLoading])

  const create = useMutation({
    mutationFn: async (data: { name: string; description: string }) => {
      console.log('Creating project:', data)
      const result = await api.createProject(data)
      console.log('Project created:', result)
      return result
    },
    onSuccess: (res) => {
      console.log('Creation successful, closing modal and refetching')
      setOpen(false)
      setName('')
      setDescription('')
      setError(null)
      // Force immediate refetch
      refetch()
    },
    onError: (err: any) => {
      console.error('Creation failed:', err)
      setError(err.message || 'Failed to create project')
    },
  })

  const handleCreate = () => {
    setError(null)
    create.mutate({ name, description })
  }

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress />
          <Typography sx={{ mt: 2 }}>Loading projects...</Typography>
        </Box>
      </Box>
    )
  }

  if (queryError) {
    return (
      <Box>
        <Alert severity="error">
          Failed to load projects: {(queryError as any).message}
        </Alert>
      </Box>
    )
  }

  const projectsArray = Array.isArray(projects) ? projects : []
  const hasProjects = projectsArray.length > 0

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Projects</Typography>
        <Button variant="contained" onClick={() => setOpen(true)}>
          New Project
        </Button>
      </Box>

      {/* Debug info - remove after testing */}
      <Alert severity="info" sx={{ mb: 2 }}>
        Debug: Projects loaded = {projectsArray.length} |
        isArray = {String(Array.isArray(projects))} |
        type = {typeof projects}
        <br />
        Raw data: {JSON.stringify(projects)}
      </Alert>

      {!hasProjects && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No projects yet. Click "New Project" to create your first one.
        </Alert>
      )}

      <List>
        {projectsArray.map((p: any) => (
          <ListItemButton key={p.id} onClick={() => navigate(`/projects/${p.id}`)}>
            <ListItemText
              primary={p.name || 'Untitled'}
              secondary={p.description || 'No description'}
            />
          </ListItemButton>
        ))}
      </List>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Project</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}
          <TextField
            fullWidth
            label="Project Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            sx={{ mb: 2 }}
            autoFocus
            required
          />
          <TextField
            fullWidth
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            rows={3}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={create.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!name.trim() || create.isPending}
            startIcon={create.isPending ? <CircularProgress size={20} /> : null}
          >
            {create.isPending ? 'Creating...' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
