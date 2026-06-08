// Dropzone — drag-and-drop / click-to-pick area for an OFX or QFX file.
//
// Self-contained: holds only the local "is something being dragged over me"
// highlight state. On drop or file-input change it hands the FIRST selected
// file to the parent via onFile and does no parsing itself.

import { useRef, useState } from 'react'

interface DropzoneProps {
  onFile: (file: File) => void
  disabled?: boolean
}

export default function Dropzone({ onFile, disabled = false }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const openPicker = () => {
    if (disabled) return
    inputRef.current?.click()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const file = e.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div>
      <button
        type="button"
        aria-label="Upload OFX or QFX file"
        aria-disabled={disabled}
        disabled={disabled}
        onClick={openPicker}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={
          'flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-200 disabled:cursor-not-allowed disabled:opacity-60 ' +
          (dragOver
            ? 'border-emerald-400 bg-emerald-50'
            : 'border-slate-300 bg-white hover:border-emerald-300 hover:bg-slate-50')
        }
      >
        <span className="text-sm font-medium text-slate-700">
          Drag &amp; drop an OFX or QFX file here
        </span>
        <span className="text-xs text-slate-500">
          or click to choose a file
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".ofx,.qfx"
        className="hidden"
        aria-label="OFX or QFX file input"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
          // Reset so picking the same file again still fires onChange.
          e.target.value = ''
        }}
      />
    </div>
  )
}
