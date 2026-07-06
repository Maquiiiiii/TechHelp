import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webmanifest}'],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes('/api/v1/tickets'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'tickets-api-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 24 * 60 * 60 // Validez de la caché: 24 horas
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          }
        ]
      },
      manifest: {
        name: 'TechHelp PWA',
        short_name: 'TechHelp',
        description: 'TechHelp Corporativo Soporte Técnico',
        theme_color: '#1A1D20',
        background_color: '#1A1D20',
        display: 'standalone',
        orientation: 'portrait'
      }
    })
  ]
})