import { useRef, useState } from 'react'
import { usePantryMutations } from '../../hooks/usePantry'
import { useWhisper } from '../../hooks/useWhisper'
import { blobToPcm16k } from '../../lib/audio'
import { track } from '../../lib/analytics'
import { Button } from '../ui/Button'

interface VoiceInputProps {
  onResult: (r: { added: string[]; skipped: string[] }) => void
  onError: (msg: string) => void
  onClear: () => void
}

export function VoiceInput({ onResult, onError, onClear }: VoiceInputProps) {
  const { transcribe, status, progress } = useWhisper()
  const { parse } = usePantryMutations()

  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [dragOver, setDragOver] = useState(false)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const processBlob = async (blob: Blob) => {
    onClear()
    setTranscribing(true)
    try {
      const pcm = await blobToPcm16k(blob)
      const text = await transcribe(pcm)
      setTranscript(text)
      if (!text) onError("Didn't catch any speech — try again or speak a little longer.")
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Transcription failed.')
    } finally {
      setTranscribing(false)
    }
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = e => { if (e.data.size) chunksRef.current.push(e.data) }
      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        void processBlob(new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' }))
      }
      recorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch {
      onError('Could not access the microphone. Check permissions, or drop an audio file.')
    }
  }

  const stopRecording = () => {
    recorderRef.current?.stop()
    setRecording(false)
  }

  const handleAdd = async () => {
    if (!transcript.trim()) return
    try {
      const res = await parse.mutateAsync(transcript)
      track('pantry_parsed', { source: 'voice', added: res.added.length })
      onResult(res)
      if (res.added.length > 0) setTranscript('')
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Could not add — try again.')
    }
  }

  const busy = transcribing || recording

  const statusLine = transcribing
    ? status === 'loading'
      ? `Loading voice model… ${progress}% (one-time)`
      : 'Transcribing…'
    : null

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        Say what you have, e.g. "two pounds of chicken, a dozen eggs, some rice." Runs locally in your browser.
      </p>

      {/* Capture controls */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault(); setDragOver(false)
          const f = e.dataTransfer.files?.[0]
          if (f && f.type.startsWith('audio/')) void processBlob(f)
        }}
        className={`border-2 border-dashed rounded-xl px-4 py-6 text-center transition-colors ${
          dragOver ? 'border-emerald-500 bg-emerald-500/5' : 'border-slate-700'
        }`}
      >
        <div className="flex items-center justify-center gap-2">
          {recording ? (
            <Button variant="danger" size="sm" onClick={stopRecording}>
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" /> Stop recording
            </Button>
          ) : (
            <Button variant="secondary" size="sm" onClick={startRecording} disabled={busy}>
              <span className="w-2 h-2 rounded-full bg-rose-500" /> Record
            </Button>
          )}
          <span className="text-xs text-slate-600">or</span>
          <Button variant="secondary" size="sm" onClick={() => fileInputRef.current?.click()} disabled={busy}>
            Drop / choose audio
          </Button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) void processBlob(f); e.target.value = '' }}
        />
        {statusLine && (
          <div className="flex items-center justify-center gap-2 mt-3 text-xs text-emerald-400">
            <span className="w-3 h-3 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            {statusLine}
          </div>
        )}
      </div>

      {/* Editable transcript */}
      {transcript && !transcribing && (
        <div className="space-y-2">
          <label className="text-xs text-slate-500">Heard this — edit if needed, then add:</label>
          <textarea
            value={transcript}
            onChange={e => setTranscript(e.target.value)}
            rows={3}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 resize-none focus:outline-none focus:border-emerald-500"
          />
          <Button variant="primary" onClick={handleAdd} loading={parse.isPending} disabled={!transcript.trim()} className="w-full">
            Add to pantry
          </Button>
        </div>
      )}
    </div>
  )
}
