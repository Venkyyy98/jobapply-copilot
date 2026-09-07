import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { loadEnvConfig } = require("@next/env");

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
loadEnvConfig(projectRoot);
