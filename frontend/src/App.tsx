import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/lib/auth-context'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import SignIn from '@/pages/SignIn'
import Chat from '@/pages/Chat'
import Sidebar from '@/components/Sidebar'

function HomeLayout() {
  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <main className="flex-1 flex items-center justify-center px-8">
        <div className="text-center max-w-2xl">
          <h1 className="text-4xl font-bold mb-4">Start a conversation</h1>
          <p className="text-foreground/60">
            Choose an existing thread from the sidebar or create a new chat to ask questions about SEC filings.
          </p>
        </div>
      </main>
    </div>
  )
}

function ChatLayout() {
  return (
    <div className="flex h-screen bg-background">
      <Sidebar />
      <Chat />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/signin" element={<SignIn />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <HomeLayout />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat/:threadId"
            element={
              <ProtectedRoute>
                <ChatLayout />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
