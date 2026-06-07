import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { pantryApi } from '../api/pantry'

export function usePantry() {
  return useQuery({ queryKey: ['pantry'], queryFn: pantryApi.list })
}

export function usePantryMutations() {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['pantry'] })
    qc.invalidateQueries({ queryKey: ['grocery'] })
  }

  const add = useMutation({ mutationFn: pantryApi.add, onSuccess: invalidate })
  const remove = useMutation({ mutationFn: pantryApi.remove, onSuccess: invalidate })
  const clear = useMutation({ mutationFn: pantryApi.clear, onSuccess: invalidate })
  const parse = useMutation({ mutationFn: pantryApi.parse, onSuccess: invalidate })
  const deplete = useMutation({ mutationFn: pantryApi.deplete, onSuccess: invalidate })

  return { add, remove, clear, parse, deplete }
}
