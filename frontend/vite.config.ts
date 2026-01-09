import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import svgr from "vite-plugin-svgr";

// https://vite.dev/config/
export default defineConfig({
  base: "/",
  plugins: [
    react(),
    svgr({
      svgrOptions: {
        icon: true,
        // This will transform your SVG to a React component
        exportType: "named",
        namedExport: "ReactComponent",
      },
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        // Code splitting - separate vendor chunks
        manualChunks: {
          // Core React libraries
          "vendor-react": ["react", "react-dom", "react-router"],
          // UI libraries
          "vendor-ui": ["react-hot-toast", "clsx", "tailwind-merge"],
          // Heavy charting libraries - load separately
          "vendor-charts": ["apexcharts", "react-apexcharts"],
          // Calendar (heavy)
          "vendor-calendar": [
            "@fullcalendar/core",
            "@fullcalendar/daygrid",
            "@fullcalendar/react",
            "@fullcalendar/interaction",
          ],
          // Drag and drop
          "vendor-dnd": ["react-dnd", "react-dnd-html5-backend"],
        },
      },
    },
    // Increase chunk size warning limit slightly (default 500kb)
    chunkSizeWarningLimit: 600,
  },
});
