import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './components/Login'
import TaskDashboard from './components/TaskDashboard'
import './App.css'

function AppContent() {
  const { user } = useAuth()
  return user ? <TaskDashboard /> : <Login />
}

export default function App() {
  return (
    <AuthProvider>
      <main className="app">
        <AppContent />
      </main>
    </AuthProvider>
  )
}
