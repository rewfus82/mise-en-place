import { useRef, useState } from 'react'
import { track } from '../../lib/analytics'
import { usePantryMutations } from '../../hooks/usePantry'
import { fileToResizedJpeg } from '../../lib/image'
import { Button } from '../ui/Button'
import { CameraCapture } from './CameraCapture'
import { VoiceInput } from './VoiceInput'

type Mode = 'text' | 'photo' | 'voice'
type ParseResult = { added: string[]; skipped: string[] }

export function PantryParser() {
  const [mode, setMode] = useState<Mode>('text')
  const [result, setResult] = useState<ParseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // text mode
  const [text, setText] = useState('')

  // photo mode
  const [photo, setPhoto] = useState<{ file: File; preview: string } | null>(null)
  const [showCamera, setShowCamera] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { parse, parseImage } = usePantryMutations()

  const switchMode = (m: Mode) => {
    setMode(m)
    setResult(null)
    setError(null)
  }

  const handleParseText = async () => {
    setError(null)
    try {
      const res = await parse.mutateAsync(text)
      track('pantry_parsed', { source: 'text', added: res.added.length })
      setResult(res)
      if (res.added.length > 0) setText('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not parse — try again.')
    }
  }

  const pickPhoto = (file: File) => {
    setResult(null)
    if (photo) URL.revokeObjectURL(photo.preview)
    setPhoto({ file, preview: URL.createObjectURL(file) })
    setShowCamera(false)
  }

  const clearPhoto = () => {
    if (photo) URL.revokeObjectURL(photo.preview)
    setPhoto(null)
  }

  const handleScanPhoto = async () => {
    if (!photo) return
    setError(null)
    try {
      const { data, mimeType } = await fileToResizedJpeg(photo.file)
      const res = await parseImage.mutateAsync({ data, mimeType })
      track('pantry_parsed', { source: 'photo', added: res.added.length })
      setResult(res)
      if (res.added.length > 0) clearPhoto()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read the photo — try a clearer shot.')
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
      {/* Mode tabs */}
      <div className="flex items-center gap-1 bg-slate-800/60 rounded-lg p-0.5 w-fit">
        {([['text', 'Describe'], ['photo', 'Photo'], ['voice', 'Voice']] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => switchMode(m)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              mode === m ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Text mode */}
      {mode === 'text' && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500">Type naturally, e.g. "2 lbs chicken breast, a dozen eggs, 1 cup rice"</p>
          <textarea
            value={text}
            onChange={e => { setText(e.target.value); setResult(null); setError(null) }}
            placeholder="Describe what you have..."
            rows={3}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-emerald-500"
          />
          <Button variant="primary" onClick={handleParseText} loading={parse.isPending} disabled={!text.trim()}>
            Parse & Add
          </Button>
        </div>
      )}

      {/* Photo mode */}
      {mode === 'photo' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Snap or drop a photo of your groceries, fridge, or a receipt.</p>

          {!photo ? (
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => {
                e.preventDefault(); setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f && f.type.startsWith('image/')) pickPhoto(f)
              }}
              className={`border-2 border-dashed rounded-xl px-4 py-8 text-center transition-colors ${
                dragOver ? 'border-emerald-500 bg-emerald-500/5' : 'border-slate-700'
              }`}
            >
              <p className="text-sm text-slate-400 mb-3">Drag an image here, or</p>
              <div className="flex items-center justify-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => fileInputRef.current?.click()}>
                  Choose file
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setShowCamera(true)}>
                  Take photo
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) pickPhoto(f); e.target.value = '' }}
              />
            </div>
          ) : (
            <div className="space-y-2">
              <div className="relative">
                <img src={photo.preview} alt="pantry" className="w-full max-h-64 object-contain rounded-xl bg-slate-950" />
                <button
                  onClick={clearPhoto}
                  className="absolute top-2 right-2 w-7 h-7 rounded-full bg-slate-950/80 text-slate-300 hover:text-white flex items-center justify-center cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16">
                    <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
              <Button variant="primary" onClick={handleScanPhoto} loading={parseImage.isPending} className="w-full">
                {parseImage.isPending ? 'Scanning photo…' : 'Scan photo'}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Voice mode */}
      {mode === 'voice' && (
        <VoiceInput
          onResult={setResult}
          onError={setError}
          onClear={() => { setResult(null); setError(null) }}
        />
      )}

      {/* Error */}
      {error && (
        <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* Shared result */}
      {result && (
        <div className="space-y-1 text-xs">
          {result.added.length > 0 && (
            <div className="text-emerald-400">Added: {result.added.join(', ')}</div>
          )}
          {result.skipped.length > 0 && (
            <div className="text-amber-400">Already on file: {result.skipped.join(', ')}</div>
          )}
          {result.added.length === 0 && result.skipped.length === 0 && (
            <div className="text-slate-500">No food items detected — try a clearer shot or describe them.</div>
          )}
        </div>
      )}

      {showCamera && <CameraCapture onCapture={pickPhoto} onClose={() => setShowCamera(false)} />}
    </div>
  )
}
