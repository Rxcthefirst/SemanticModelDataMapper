import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material'

import Layout from './components/layout/Layout'
import ProjectList from './pages/ProjectList'
import ProjectDetail from './pages/ProjectDetail'

const queryClient = new QueryClient()

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<ProjectList />} />
              <Route path="/projects/:id" element={<ProjectDetail />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App

