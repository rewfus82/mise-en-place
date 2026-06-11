// Resize/compress an image file to a base64 JPEG before upload, so a full-res phone
// photo doesn't blow up vision-model token cost. Returns base64 without the data: prefix.

export async function fileToResizedJpeg(
  file: File | Blob,
  maxDim = 1024,
  quality = 0.85,
): Promise<{ data: string; mimeType: string }> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(fr.result as string)
    fr.onerror = () => reject(new Error('Could not read image'))
    fr.readAsDataURL(file)
  })

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const i = new Image()
    i.onload = () => resolve(i)
    i.onerror = () => reject(new Error('Could not load image'))
    i.src = dataUrl
  })

  const scale = Math.min(1, maxDim / Math.max(img.width, img.height))
  const w = Math.max(1, Math.round(img.width * scale))
  const h = Math.max(1, Math.round(img.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')
  ctx.drawImage(img, 0, 0, w, h)

  const out = canvas.toDataURL('image/jpeg', quality)
  return { data: out.split(',')[1], mimeType: 'image/jpeg' }
}
