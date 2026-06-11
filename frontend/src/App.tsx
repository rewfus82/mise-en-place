import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { track, trackPageView } from './lib/analytics'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { AppShell } from './components/layout/AppShell'
import { CalendarPage } from './pages/CalendarPage'
import { PantryPage } from './pages/PantryPage'
import { GroceryPage } from './pages/GroceryPage'
import { ProfilePage } from './pages/ProfilePage'
import { CoachPage } from './pages/CoachPage'
import { OnboardingWizard } from './components/onboarding/OnboardingWizard'
import { DailyConfirmModal } from './components/confirmation/DailyConfirmModal'
import { useDailyPrompt } from './hooks/useDailyPrompt'
import { profileApi } from './api/profile'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ToastProvider } from './components/ui/Toast'
import { PlanningProvider } from './context/PlanningContext'
import { CoachProvider } from './context/CoachContext'
import { PlanningPill } from './components/PlanningPill'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

function RouteTracker() {
  const location = useLocation()
  useEffect(() => {
    trackPageView(location.pathname)
  }, [location.pathname])
  return null
}

function ThemeSync() {
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })

  useEffect(() => {
    const theme = profile?.theme ?? localStorage.getItem('theme') ?? 'dark'
    if (theme === 'light') {
      document.documentElement.classList.remove('dark')
    } else {
      document.documentElement.classList.add('dark')
    }
  }, [profile?.theme])

  return null
}

function DailyPromptGate() {
  const { shouldShow, unconfirmedDays, markChecked } = useDailyPrompt()

  if (!shouldShow) return null

  return (
    <DailyConfirmModal
      days={unconfirmedDays}
      onDone={markChecked}
    />
  )
}

function AppRoutes() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: profileApi.get,
  })

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const needsOnboarding = !profile?.weight_kg || !profile?.goal || profile.goal === 'maintain' && !profile.calorie_target

  if (needsOnboarding) {
    return (
      <OnboardingWizard
        onComplete={() => {
          track('onboarding_completed')
          queryClient.invalidateQueries({ queryKey: ['profile'] })
        }}
      />
    )
  }

  return (
    <>
      <DailyPromptGate />
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Navigate to="/calendar" replace />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="pantry" element={<PantryPage />} />
          <Route path="grocery" element={<GroceryPage />} />
          <Route path="coach" element={<CoachPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/calendar" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ToastProvider>
            <PlanningProvider>
              <CoachProvider>
                <RouteTracker />
                <ThemeSync />
                <AppRoutes />
                <PlanningPill />
              </CoachProvider>
            </PlanningProvider>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
