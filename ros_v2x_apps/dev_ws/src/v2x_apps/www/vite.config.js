import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/www/',
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        index: 'index.html',
        map: 'map.html',
      },
    },
  },
})
