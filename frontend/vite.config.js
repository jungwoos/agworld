import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    outDir: '../agworld/static',
    emptyOutDir: true,
  },
  base: './',
})