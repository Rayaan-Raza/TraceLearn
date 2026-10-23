import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

w("frontend/package.json", json.dumps({
    "name": "tracelearn-frontend", "private": True, "version": "0.1.0", "type": "module",
    "scripts": {"dev": "vite", "build": "tsc -b && vite build", "preview": "vite preview"},
    "dependencies": {"@monaco-editor/react": "^4.7.0", "react": "^19.0.0", "react-dom": "^19.0.0"},
    "devDependencies": {"@types/react": "^19.0.0", "@types/react-dom": "^19.0.0", "@vitejs/plugin-react": "^4.3.4", "typescript": "~5.7.2", "vite": "^6.0.0"}
}, indent=2))
w("frontend/tsconfig.json", '{"files":[],"references":[{"path":"./tsconfig.app.json"},{"path":"./tsconfig.node.json"}]}')
w("frontend/tsconfig.app.json", '{"compilerOptions":{"target":"ES2020","useDefineForClassFields":true,"lib":["ES2020","DOM","DOM.Iterable"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"jsx":"react-jsx","strict":true,"noUnusedLocals":false,"noUnusedParameters":false,"noFallthroughCasesInSwitch":true,"noUncheckedSideEffectImports":true},"include":["src"]}')
w("frontend/tsconfig.node.json", '{"compilerOptions":{"target":"ES2022","lib":["ES2023"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"strict":true,"noUncheckedSideEffectImports":true},"include":["vite.config.ts"]}')
w("frontend/vite.config.ts", "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\nexport default defineConfig({ plugins: [react()], server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' } } })\n")
w("frontend/index.html", '<!doctype html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>TraceLearn POC</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>')
w("frontend/src/main.tsx", "import { StrictMode } from 'react'\nimport { createRoot } from 'react-dom/client'\nimport App from './App'\nimport './styles.css'\ncreateRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)\n")
w("frontend/src/vite-env.d.ts", '/// <reference types="vite/client" />\n')
print("frontend scaffold ok")
