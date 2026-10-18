import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { ModelSettingsProvider } from '@/context/ModelSettingsContext'
import Home from '@/pages/Home'
import Result from '@/pages/Result'
import History from '@/pages/History'

export default function App() {
  return (
    <AuthProvider>
      <ModelSettingsProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/result/:jobId" element={<Result />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </BrowserRouter>
      </ModelSettingsProvider>
    </AuthProvider>
  )
}
