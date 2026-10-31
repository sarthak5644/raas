import React, { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import useAuthStore from './store/authStore'
import AppLayout from './components/layout/AppLayout'

// Pages
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import FilesPage from './pages/FilesPage'
import AnalysisPage from './pages/AnalysisPage'
import PricingPage from './pages/PricingPage'
import ProfilePage from './pages/ProfilePage'
import AdminLoginPage from './pages/AdminLoginPage'
import AdminDashboardPage from './pages/AdminDashboardPage'

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children
}

export default function App() {
  const { refreshUser, isAuthenticated } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated) {
      refreshUser().catch(() => {})
    }
  }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#F7F2FB',
            color: '#241B33',
            border: '1px solid rgba(107,45,139,0.10)',
            borderRadius: '12px',
            fontFamily: 'Space Grotesk, sans-serif',
            fontSize: '14px',
          },
          success: { iconTheme: { primary: '#16A34A', secondary: '#F7F2FB' } },
          error: { iconTheme: { primary: '#DC2626', secondary: '#F7F2FB' } },
        }}
      />
      <Routes>
        {/* Public */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/pricing" element={<PricingPage standalone />} />

        {/* Protected */}
        <Route path="/dashboard" element={<ProtectedRoute><AppLayout><DashboardPage /></AppLayout></ProtectedRoute>} />
        <Route path="/upload" element={<ProtectedRoute><AppLayout><UploadPage /></AppLayout></ProtectedRoute>} />
        <Route path="/files" element={<ProtectedRoute><AppLayout><FilesPage /></AppLayout></ProtectedRoute>} />
        <Route path="/analysis/:fileId" element={<ProtectedRoute><AppLayout><AnalysisPage /></AppLayout></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><AppLayout><ProfilePage /></AppLayout></ProtectedRoute>} />

        {/* Admin Panel — separate auth, separate token (admin_token) */}
        <Route path="/admin/login" element={<AdminLoginPage />} />
        <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        <Route path="/admin" element={<Navigate to="/admin/login" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}