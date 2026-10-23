from pathlib import Path

root = Path(r"c:\Users\rayaan\Desktop\POC\frontend")
src = root / "src"
screens = src / "screens"
screens.mkdir(parents=True, exist_ok=True)

(root / "vite.config.ts").write_text(
    """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
""",
    encoding="utf-8",
)

(root / "index.html").write_text(
    """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>TraceLearn</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
    encoding="utf-8",
)

print("base files ok")
