// Decode an audio blob/file (recorded webm/opus, or an uploaded mp3/wav/m4a) into the
// 16 kHz mono Float32 PCM that Whisper expects. Decoding + resampling happens on the
// main thread (Web Audio), then the Float32Array is transferred to the worker.

export async function blobToPcm16k(blob: Blob): Promise<Float32Array> {
  const arrayBuffer = await blob.arrayBuffer()

  const AudioCtx: typeof AudioContext =
    window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const decodeCtx = new AudioCtx()
  let decoded: AudioBuffer
  try {
    decoded = await decodeCtx.decodeAudioData(arrayBuffer)
  } finally {
    void decodeCtx.close()
  }

  const targetRate = 16000
  const frames = Math.ceil(decoded.duration * targetRate)
  // Mono (1 channel) destination auto-downmixes; targetRate resamples.
  const offline = new OfflineAudioContext(1, frames, targetRate)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()
  const rendered = await offline.startRendering()
  return rendered.getChannelData(0)
}
