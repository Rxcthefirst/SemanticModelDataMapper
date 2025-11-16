import React from 'react'
import { Box, AppBar, Toolbar, Typography, Container } from '@mui/material'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            RDFMap
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4, flex: 1 }}>
        {children}
      </Container>
    </Box>
  )
}

