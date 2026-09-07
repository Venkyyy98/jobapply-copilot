import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { loadEnvConfig } = require("@next/env");
const __dirname = dirname(fileURLToPath(import.meta.url));
loadEnvConfig(resolve(__dirname, ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  typedRoutes: false
};

export default nextConfig;
