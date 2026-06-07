import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { groceryApi } from '../api/grocery'

export function useGrocery() {
  return useQuery({ queryKey: ['grocery'], queryFn: groceryApi.list })
}

export function useGroceryMutations() {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['grocery'] })
    qc.invalidateQueries({ queryKey: ['pantry'] })
  }

  const ignore = useMutation({ mutationFn: groceryApi.ignore, onSuccess: invalidate })
  const markBought = useMutation({
    mutationFn: ({ item, quantity, category }: { item: string; quantity: string; category?: string }) =>
      groceryApi.markBought(item, quantity, category),
    onSuccess: invalidate,
  })

  return { ignore, markBought }
}
