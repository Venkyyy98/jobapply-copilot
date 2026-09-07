# Resume Formatting, Testing, and Sharing

## What Changed

Both resume exports now normalize the generated text into one `ResumeDocument` containing typed blocks and inline segments. PDF and DOCX consume the same blocks, including bold text and links. The text adapter preserves stored resume text and the existing API contract.

Root causes and fixes:

| Problem | Cause | Fix |
| --- | --- | --- |
| Inconsistent fonts | OS-specific Times font discovery and independent DOCX run styling | Package Liberation Sans regular/bold fonts, embed them in both formats, and explicitly style every run. Liberation Sans is an Arial-compatible sans-serif font. |
| Missing bold titles | Each exporter inferred headings, roles, and education differently | Parse role, company, degree, institution, skill label, and project fields once; apply bold in code. |
| No bullet emphasis | Exporters treated bullets as plain text | Convert paired legacy Markdown to validated segments; otherwise select up to two existing technology/capability/metric phrases. No added facts or LLM formatting dependency. |
| Lost links | PDF project links were only colored labels | Both exporters create actual hyperlink relationships/annotations. |
| Wrong dates or crowded headers | Different heuristics and Word tab stops | Use narrow, borderless title/date rows with right-aligned dates and wrapping. Body content remains single-column text. |
| Tiny text and layout drift | PDF-only fit checks allowed 8.6-point text; Word added border spacing | Shared 10-point default / 9.5-point compact typography, consistent borders and spacing. Preserve multiple pages when content cannot reasonably fit. |
| Random plain output | `/generate_docs` caught formatting failures and used unstyled converters | Return a clear error for failed resume exports. Cover-letter behavior is unchanged. |

Changed source files for this fix:

- `server/app/resume_document.py`: canonical blocks, safe links, text normalization, selective emphasis.
- `server/app/resume_export.py`: shared typography, embedded fonts, PDF/DOCX adapters and layout choice.
- `server/app/exporters.py`: compatibility entry points; removed duplicate resume renderers.
- `server/app/main.py`: formatted-export error handling and overflow notice.
- `server/data/templates/resume_template.jinja2`: stable experience fields with optional location/dates.
- `server/app/fonts/LiberationSans-Regular.ttf`, `LiberationSans-Bold.ttf`, `LICENSE_LIBERATION`: portable font assets and redistribution license.
- `server/pyproject.toml`: include fonts in package distributions.
- `server/tests/test_resume_exports.py`: formatting, emphasis, escaping, fonts, dates, empty fields, long content, links, and generation API regression tests.
- `scripts/preview_resumes.py`: repeatable offline previews for four roles.
- `README.md` and this guide: testing and beta instructions.

## Generation Flow and API Keys

The Chrome extension calls `POST /generate_docs` through `extension/service_worker.js`. FastAPI parses the job, creates a tailoring plan, rewrites selected experience/project content, renders the Jinja text template, checks claims, and exports the resume. Download endpoints remain `/download/{job_id}/resume_pdf` and `/download/{job_id}/resume_docx`.

The Next.js website currently provides profiles, job details, saved application tracking, and account/token controls. `web/app/jobs/[id]/page.tsx` explicitly directs final generation to the extension. There is no separate web resume HTML/CSS/PDF renderer to fix; website CSS does not style downloaded resumes.

The request key is supplied through `X-OpenAI-API-Key`. The server's generation response exposes `ai_assisted`, `ai_key_source`, and `generation_warnings`. `ai_assisted=true` means at least one AI call succeeded during generation; it does not prove every bullet was rewritten. Some original project bullets may intentionally be retained. Generation speed alone does not establish whether AI was used.

The previews below make no OpenAI requests. They test deterministic role selection and the actual exporters. A live BYOK run is a separate acceptance test.

## Test Locally

Run from the repository root:

```bash
./.venv/bin/pytest -q server/tests
./.venv/bin/python scripts/preview_resumes.py
```

If setting up a new machine, create a Python virtual environment and install `pip install -e './server[dev]'` first. The preview script uses your local candidate profile by default. For another factual profile:

```bash
./.venv/bin/python scripts/preview_resumes.py --profile /absolute/path/candidate.yaml --output output/custom-previews
```

Generated pairs are under `output/resume-previews/`:

| Role | PDF | DOCX |
| --- | --- | --- |
| AI/ML Engineer | `ai_ml_engineer.pdf` | `ai_ml_engineer.docx` |
| Data Engineer | `data_engineer.pdf` | `data_engineer.docx` |
| Data Scientist | `data_scientist.pdf` | `data_scientist.docx` |
| Business Analyst | `business_analyst.pdf` | `business_analyst.docx` |

Start the API from the repository root when testing through Chrome:

```bash
./.venv/bin/uvicorn server.app.main:app --host 127.0.0.1 --port 8787 --reload
```

Keep one API process and one Next.js process running. If Next.js reports that port 3000 is already in use, stop the PID printed in that message, then run `npm run dev` once from `web/`.

Start the web app in another terminal:

```bash
cd web
npm run dev
```

Then perform this acceptance test for one real posting in each role family:

1. Sign in, save your factual profile at `/app/profile`, and create an extension token at `/install-extension`.
2. Set the API URL and extension token in extension Options. Enter your own OpenAI key in the extension's key controls. The extension token and the OpenAI key have different purposes.
3. Open the posting, analyze it, and confirm the company, title, and location. Use edited details if needed.
4. Generate fresh documents. Existing downloaded PDFs/DOCXs are not automatically reformatted.
5. Inspect the extension's AI status and warnings. For BYOK, expect `ai_key_source=byok` and a successful AI indication. Use the extension service-worker Network inspector if you need the raw `/generate_docs` response. A template warning means the live AI acceptance test has not passed.
6. Open both formats. Check titles, school names, technical-skill labels, restrained bullet emphasis, phone formatting, right-aligned dates, and clickable GitHub/LinkedIn links. Verify that source facts, metrics, and the research-assistant title remain correct.
7. Compare role-relevant skills and projects against the job description. Missing qualifications should remain missing unless your saved profile supports them.
8. Mark the job applied and confirm it appears in your tracker with the correct date and search results.

Visual QA for this change uses Poppler for PDF PNGs and the document skill's `render_docx.py` (bundled LibreOffice) for Word PNGs. Word and ReportLab may differ slightly in line wrapping and baseline placement; font embedding cannot make their layout engines identical. Overflow detection uses PDF measurement, so inspect Word too after unusually long content changes. All four current role samples were checked in both formats.

## Let Other People Try It

Use local testing first, then a hosted private beta. `127.0.0.1` points to each person's own machine, so sending someone your localhost link will not connect them to your app.

For a trusted tester who runs everything locally, provide the repository, its setup instructions, and the extension package. They need their own configuration, Google sign-in setup, profile, and API key. Do not distribute your personal `.env`, candidate YAML, database, or generated resumes.

For testers who should only need a browser:

1. Host the API and the Next.js website at public HTTPS addresses. The repository contains a Render API configuration and a Dockerfile; deployment has not been performed as part of this formatting fix.
2. Configure persistent storage before inviting testers. The current database is SQLite; keep a single API instance with a persistent disk and backups. Set `JAC_DB_PATH` and `JAC_OUTPUT_DIR` to that disk. The existing `render.yaml` does not provision a persistent disk. Multiple API replicas need a shared database/storage implementation, not separate SQLite files.
3. Configure the web app's `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, Google OAuth credentials, and `NEXT_PUBLIC_API_BASE_URL`. Register the web origin's `/api/auth/callback/google` as the OAuth callback. Keep the signing secret stable across restarts.
4. Configure API `JAC_CORS_ORIGINS` for the hosted web origin, the same hosted API base URL, and the server-to-server `JAC_TOKEN`. Keep `JAC_ALLOW_SERVER_LLM_FALLBACK=false` for BYOK. Keep server secrets out of the extension package.
5. Each tester signs in, saves their own profile, creates their own extension token, installs the extension, and enters the hosted API URL, their extension token, and their own OpenAI key.
6. Test with two different accounts: profiles, applications, and downloads must remain private to each account. Then run the same role-generation and tracker acceptance test above.

Package the current extension:

```bash
./scripts/package_extension.sh
```

This reads the version from `extension/manifest.json` and writes `dist/jobapply-copilot-extension-v0.1.1.zip`. Trusted testers unzip it, open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select the extracted folder containing `manifest.json`. For wider distribution, publish a reviewed Chrome Web Store listing and configure `NEXT_PUBLIC_CHROME_EXTENSION_URL` with its actual URL.

Do not send the entire working-directory ZIP: it may contain personal data. The packaging script includes only extension source files.
