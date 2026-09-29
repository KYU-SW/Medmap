import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webDirectory = path.dirname(fileURLToPath(import.meta.url));
const certificateDirectory = path.resolve(webDirectory, "../../local-cache/mobile-https");
const certificatePath = path.join(certificateDirectory, "server-cert.pem");
const keyPath = path.join(certificateDirectory, "server-key.pem");
const https = existsSync(certificatePath) && existsSync(keyPath)
  ? { cert: readFileSync(certificatePath), key: readFileSync(keyPath) }
  : undefined;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    https,
    proxy: {
      "/v1": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000"
    }
  }
});
