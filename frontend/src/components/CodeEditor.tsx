/**
 * Monaco editor bundled locally (no CDN loader), so the strict CSP
 * (script-src 'self') holds and no third party sees student code.
 * This module is lazy-loaded: Monaco only downloads on the problem page.
 */
import Editor, { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'

self.MonacoEnvironment = { getWorker: () => new EditorWorker() }
loader.config({ monaco })

monaco.editor.defineTheme('tracelearn', {
  base: 'vs-dark',
  inherit: true,
  rules: [],
  colors: {
    'editor.background': '#2e2930',
    'editor.foreground': '#e4d2d8',
    'editorLineNumber.foreground': '#7a7183',
    'editor.lineHighlightBackground': '#3a343d',
  },
})

export default function CodeEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height = 380,
}: {
  value: string
  onChange?: (v: string) => void
  language: string
  readOnly?: boolean
  height?: number
}) {
  return (
    <div className="monaco-wrap">
      <Editor
        height={height}
        language={language === 'cpp' ? 'cpp' : 'python'}
        theme="tracelearn"
        value={value}
        onChange={(v) => onChange?.(v ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          padding: { top: 12, bottom: 12 },
          fontFamily: "'Cascadia Code', 'Fira Code', Consolas, monospace",
        }}
      />
    </div>
  )
}
