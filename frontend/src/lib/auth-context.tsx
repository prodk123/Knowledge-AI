"use client"

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react"
import { useRouter, usePathname } from "next/navigation"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type Permission = {
  name: string
}

type Role = {
  name: string
  permissions: Permission[]
}

export type User = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  roles: Role[]
}

type AuthContextType = {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
  hasPermission: (permissionName: string) => boolean
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const storedToken = localStorage.getItem("access_token")
    if (storedToken) {
      fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${storedToken}` },
      })
        .then((res) => {
          if (res.ok) return res.json()
          throw new Error("Invalid token")
        })
        .then((data) => {
          setToken(storedToken)
          setUser(data)
          setIsLoading(false)
        })
        .catch(() => {
          localStorage.removeItem("access_token")
          setToken(null)
          setUser(null)
          setIsLoading(false)
          if (pathname !== "/login" && pathname !== "/register") router.push("/login")
        })
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoading(false)
      if (pathname !== "/login" && pathname !== "/register") router.push("/login")
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = useCallback((newToken: string, userData: User) => {
    localStorage.setItem("access_token", newToken)
    setToken(newToken)
    setUser(userData)
    router.push("/")
  }, [router])

  const logout = useCallback(() => {
    localStorage.removeItem("access_token")
    setToken(null)
    setUser(null)
    router.push("/login")
  }, [router])

  const hasPermission = useCallback((permissionName: string) => {
    if (!user) return false
    for (const role of user.roles) {
      for (const p of role.permissions) {
        if (p.name === permissionName) return true
      }
    }
    return false
  }, [user])

  return (
    <AuthContext.Provider value={{ user, token, login, logout, hasPermission, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
