import { useEffect, useRef, useState } from 'react'
import { useEscapeKey } from '../../hooks/useEscapeKey'
import { Button } from '../ui/Button'

interface CameraCaptureProps {
  onCapture: (file: File) => void
  onClose: () => void
}

/** Full-screen camera capture via getUserMedia — works on mobile and desktop webcams. */
export function CameraCapture({ onCapture, onClose }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEscapeKey(onClose)

  useEffect(() => {
    let active = true
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then(stream => {
        if (!active) {
          stream.getTracks().forEach(t => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          void videoRef.current.play()
        }
      })
      .catch(() => setError('Could not access the camera. Check permissions, or use Upload instead.'))

    return () => {
      active = false
      streamRef.current?.getTracks().forEach(t => t.stop())
    }
  }, [])

  const capture = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0)
    canvas.toBlob(
      blob => {
        if (blob) onCapture(new File([blob], 'capture.jpg', { type: 'image/jpeg' }))
      },
      'image/jpeg',
      0.9,
    )
  }

  return (
    <div className="fixed inset-0 z-[70] bg-black/85 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-slate-900 border border-slate-800 rounded-2xl p-4 max-w-lg w-full"
        onClick={e => e.stopPropagation()}
      >
        {error ? (
          <div className="text-sm text-rose-400 py-10 text-center px-4">{error}</div>
        ) : (
          <video ref={videoRef} playsInline muted className="w-full rounded-xl bg-black aspect-video object-cover" />
        )}
        <div className="flex justify-between gap-2 mt-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {!error && <Button variant="primary" onClick={capture}>Capture</Button>}
        </div>
      </div>
    </div>
  )
}
