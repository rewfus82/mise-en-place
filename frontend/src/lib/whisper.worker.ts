/// <reference lib="webworker" />
// Runs Whisper entirely in-browser (transformers.js, WASM) off the main thread.
// Lazily loads the model on first transcribe and streams download progress.

import { pipeline, env, type PipelineType } from '@huggingface/transformers'

// Always fetch the model from the HF hub (no local model files bundled).
env.allowLocalModels = false

const MODEL = 'Xenova/whisper-tiny.en'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let transcriber: any = null

async function getTranscriber() {
  if (!transcriber) {
    transcriber = await pipeline('automatic-speech-recognition' as PipelineType, MODEL, {
      progress_callback: (p: unknown) => postMessage({ type: 'progress', payload: p }),
    })
    postMessage({ type: 'ready' })
  }
  return transcriber
}

onmessage = async (e: MessageEvent) => {
  const { type, audio } = e.data ?? {}
  if (type !== 'transcribe') return
  try {
    const t = await getTranscriber()
    const out = await t(audio as Float32Array, { chunk_length_s: 30, stride_length_s: 5 })
    const text = (Array.isArray(out) ? out[0]?.text : out?.text) ?? ''
    postMessage({ type: 'result', text: String(text).trim() })
  } catch (err) {
    postMessage({ type: 'error', message: err instanceof Error ? err.message : String(err) })
  }
}
