# JobApply Copilot Public Beta Launch Checklist

## Launch Positioning

JobApply Copilot is an ethical AI job application copilot that helps tailor materials and track applications while keeping final submission user-controlled.

Public beta boundaries:
- No auto-submit.
- No CAPTCHA, auth, paywall, or rate-limit bypass.
- No fabricated experience, education, certifications, work authorization, dates, or metrics.
- Users review all generated documents and field suggestions before use.

## Environments

Create three environments:
- Local: current developer machine, SQLite, unpacked extension.
- Staging: hosted API + hosted web app + test OAuth app.
- Production beta: hosted API + hosted web app + production OAuth app + packaged extension.

Recommended beta stack:
- Web: Vercel
- API: Render, Fly.io, or Railway
- Database: Supabase Postgres when moving beyond SQLite
- File storage: Cloudflare R2 or Supabase Storage
- Auth: Google OAuth through NextAuth

## Required Environment Variables

Backend/API:
- `OPENAI_API_KEY`
- `JAC_TOKEN` for local/server-to-server fallback only
- `JAC_CORS_ORIGINS`
- `JAC_ANALYZE_DAILY_QUOTA`
- `JAC_DOCS_DAILY_QUOTA`
- `JAC_OUTREACH_DAILY_QUOTA`
- `JAC_DB_PATH`
- `JAC_OUTPUT_DIR`
- `NEXT_PUBLIC_API_BASE_URL`

Web:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `NEXTAUTH_SECRET`
- `NEXTAUTH_URL`
- `NEXT_PUBLIC_API_BASE_URL`
- `JAC_TOKEN` for trusted server-to-server calls while the beta bridge is active

## Beta Smoke Test

1. Sign in to the hosted web app with Google.
2. Open `/app/profile`.
3. Save a factual candidate profile and preferences.
4. Create an extension token.
5. Paste the API base URL and token into the extension Options page.
6. Analyze a real job posting from the extension.
7. Confirm the job appears only in the signed-in user's workspace.
8. Generate documents with explicit approval.
9. Download generated documents.
10. Export user data from `/data-controls`.
11. Delete user data from `/data-controls`.

## Chrome Web Store Prep

Public users should install the extension from the Chrome Web Store. The local `extension/` folder is only for development, and ZIP/private-beta loading is only for trusted testers.

Package the extension:

```bash
./scripts/package_extension.sh
```

This creates:

```text
dist/jobapply-copilot-extension-v0.1.0.zip
```

Upload that ZIP in the Chrome Developer Dashboard. After the listing is approved, set:

```env
NEXT_PUBLIC_CHROME_EXTENSION_URL=https://chromewebstore.google.com/detail/...
```

Listing assets:
- 128x128 icon
- Screenshots showing analysis, compliance notes, document generation, and manual submission reminder
- Short description focused on compliant application assistance
- Privacy practices matching `/privacy`
- Permission explanation for active tab, scripting, storage, downloads, side panel, and host access

Review notes:
- Explain that the extension analyzes only the active page or user-provided text.
- Explain that downloads are user-triggered.
- Explain that final application submission is always manual.

## LinkedIn Launch Assets

Post structure:
- Problem: job applications are repetitive, but unsafe automation can cross lines.
- Build: Chrome extension, FastAPI tailoring engine, Next.js workspace, compliance guardrails.
- Demo: 30-60 second clip showing analyze -> compliance -> generate docs -> manual submission reminder -> tracker.
- CTA: try the beta, join waitlist, or view GitHub.

Suggested headline:
I built JobApply Copilot: an ethical AI assistant for job applications that helps tailor materials without auto-submitting or fabricating claims.

## What Costs Money

- Chrome Web Store developer registration: Google requires a one-time registration fee before publishing.
- Web hosting: Vercel can be free for early testing, but production usage may require a paid plan depending on traffic/team needs.
- API hosting: Render/Fly/Railway may have free or low-cost tiers, but reliable always-on hosting is usually paid.
- Database/storage: Supabase/Cloudflare can start free, then become paid as usage grows.
- OpenAI API: paid usage based on requests/tokens.
- Domain: optional but recommended for public launch; normally paid yearly.

Usually free for early beta:
- Google OAuth client setup.
- Local development.
- Private beta ZIP testing with trusted testers.
