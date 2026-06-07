import { useQuery } from '@tanstack/react-query'
import { profileApi } from '../api/profile'
import { ProfileForm } from '../components/profile/ProfileForm'
import { TdeeWidget } from '../components/profile/TdeeWidget'
import { MacroTargets } from '../components/profile/MacroTargets'

export function ProfilePage() {
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })
  const hasMetrics = profile?.weight_kg && profile?.height_cm && profile?.age

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Profile</h1>
        <p className="text-sm text-slate-400 mt-1">Your body metrics, goals, and meal preferences</p>
      </div>

      {hasMetrics && (
        <>
          <TdeeWidget />
          <MacroTargets />
        </>
      )}

      <ProfileForm />
    </div>
  )
}
