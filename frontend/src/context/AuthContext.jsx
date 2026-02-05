import { createContext, useContext, useState, useEffect } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }

    try {
      const response = await api.get('/auth/me')
      setUser(response.data.user)
      setCompany(response.data.company)
    } catch (error) {
      localStorage.removeItem('token')
    } finally {
      setLoading(false)
    }
  }

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password })
    const { token, user: userData, company: companyData } = response.data

    localStorage.setItem('token', token)
    setUser(userData)
    setCompany(companyData)

    return response.data
  }

  const register = async (data) => {
    const response = await api.post('/auth/register', data)
    const { token, user: userData, company: companyData } = response.data

    localStorage.setItem('token', token)
    setUser(userData)
    setCompany(companyData)

    return response.data
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
    setCompany(null)
  }

  const updateUser = (userData) => {
    setUser(prev => ({ ...prev, ...userData }))
  }

  const updateCompany = (companyData) => {
    setCompany(prev => ({ ...prev, ...companyData }))
  }

  return (
    <AuthContext.Provider value={{
      user,
      company,
      loading,
      login,
      register,
      logout,
      updateUser,
      updateCompany,
      checkAuth
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
