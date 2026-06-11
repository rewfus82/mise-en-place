import { useCallback, useEffect, useRef, useState } from 'react'

export type WhisperStatus = 'idle' | 'loading' | 'ready' | 'transcribing'

interface ProgressPayload {
  status?: string
  progress?: number
}

/**
 * Drives the in-browser Whisper worker. `transcribe` resolves with the text;
 * `status`/`progress` reflect the one-time model download and active inference.
 */
export function useWhisper() {
  const workerRef = useRef<Worker | null>(null)
  const pending = useRef<{ resolve: (t: string) => void; reject: (e: Error) => void } | null>(null)
  const [status, setStatus] = useState<WhisperStatus>('idle')
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const worker = new Worker(new URL('../lib/whisper.worker.ts', import.meta.url), { type: 'module' })
    workerRef.current = worker

    worker.onmessage = (e: MessageEvent) => {
      const msg = e.data
      if (msg.type === 'progress') {
        const p = msg.payload as ProgressPayload
        if (p.status === 'progress' && typeof p.progress === 'number') {
          setStatus('loading')
          setProgress(Math.round(p.progress))
        }
      } else if (msg.type === 'ready') {
        setStatus('ready')
        setProgress(100)
      } else if (msg.type === 'result') {
        setStatus('ready')
        pending.current?.resolve(msg.text)
        pending.current = null
      } else if (msg.type === 'error') {
        setStatus('ready')
        pending.current?.reject(new Error(msg.message))
        pending.current = null
      }
    }

    return () => {
      worker.terminate()
      workerRef.current = null
    }
  }, [])

  const transcribe = useCallback((audio: Float32Array): Promise<string> => {
    return new Promise<string>((resolve, reject) => {
      const worker = workerRef.current
      if (!worker) {
        reject(new Error('Voice model not ready'))
        return
      }
      pending.current = { resolve, reject }
      setStatus(s => (s === 'idle' ? 'loading' : 'transcribing'))
      worker.postMessage({ type: 'transcribe', audio }, [audio.buffer])
    })
  }, [])

  return { transcribe, status, progress }
}
