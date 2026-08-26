import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Convierte el frontend en una PWA instalable ("Agregar a pantalla de
    // inicio" en Android/Chrome): genera el manifest.webmanifest y un
    // service worker que solo cachea los archivos propios de la app (JS,
    // CSS, HTML, íconos) para que abra al instante aunque la conexión sea
    // mala. Las llamadas al backend (Django, en otro dominio) NUNCA se
    // cachean aquí — siempre se piden en vivo, para no mostrar nunca datos
    // desactualizados de eventos/pagos/etc.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.png', 'apple-touch-icon.png'],
      manifest: {
        name: 'COMPOINT EventFlow',
        short_name: 'EventFlow',
        description: 'Sincronía total desde el almacén hasta la mesa del invitado.',
        lang: 'es-MX',
        theme_color: '#17181a',
        background_color: '#17181a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    host: true,
  },
})
