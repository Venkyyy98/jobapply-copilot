const state = {
  currentTabId: null,
  currentJobId: null,
  currentTitle: "",
  currentCompany: "",
  docs: null,
  complianceReady: false,
  analyzeRunId: 0,
  referralDrafts: [],
  referralContactsCache: [],
  lastStableRoleTitle: "",
  lastStableCompany: "",
};

const el = {
  analyzeCurrentBtn: document.getElementById("analyzeCurrentBtn"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  generateBtn: document.getElementById("generateBtn"),
  boostBtn: document.getElementById("boostBtn"),
  checkIssueBtn: document.getElementById("checkIssueBtn"),
  markAppliedBtn: document.getElementById("markAppliedBtn"),
  exportAppliedBtn: document.getElementById("exportAppliedBtn"),
  generateReferralBtn: document.getElementById("generateReferralBtn"),
  findTargetsBtn: document.getElementById("findTargetsBtn"),
  openProfilesBtn: document.getElementById("openProfilesBtn"),
  openEmailDraftsBtn: document.getElementById("openEmailDraftsBtn"),
  referralContacts: document.getElementById("referralContacts"),
  referralOutput: document.getElementById("referralOutput"),
  referralContactSelect: document.getElementById("referralContactSelect"),
  referralDrafts: document.getElementById("referralDrafts"),
  prefillBtn: document.getElementById("prefillBtn"),
  aiFieldMode: document.getElementById("aiFieldMode"),
  jobTitle: document.getElementById("jobTitle"),
  companyHint: document.getElementById("companyHint"),
  jobText: document.getElementById("jobText"),
  spinner: document.getElementById("spinner"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  summary: document.getElementById("summary"),
  fitScore: document.getElementById("fitScore"),
  fitReasons: document.getElementById("fitReasons"),
  bulletIds: document.getElementById("bulletIds"),
  keywordCoverage: document.getElementById("keywordCoverage"),
  matchedKeywords: document.getElementById("matchedKeywords"),
  missingKeywords: document.getElementById("missingKeywords"),
  issueCard: document.getElementById("issueCard"),
  issueSummary: document.getElementById("issueSummary"),
  issueHowHelp: document.getElementById("issueHowHelp"),
  linkedinIssueBrief: document.getElementById("linkedinIssueBrief"),
  issueSources: document.getElementById("issueSources"),
  complianceNotes: document.getElementById("complianceNotes"),
  downloads: document.getElementById("downloads"),
  downloadAllBtn: document.getElementById("downloadAllBtn"),
  downloadDocxPairBtn: document.getElementById("downloadDocxPairBtn"),
  downloadPdfPairBtn: document.getElementById("downloadPdfPairBtn"),
  uploadResumeBtn: document.getElementById("uploadResumeBtn"),
  uploadCoverBtn: document.getElementById("uploadCoverBtn"),
  historyList: document.getElementById("historyList"),
};

function setStatus(msg, isError = false) {
  let text = msg || "";
  if (isError && /failed to fetch/i.test(String(text))) {
    text = "Cannot reach local server (127.0.0.1:8787). Run ./scripts/setup_and_run_server.sh";
  }
  el.status.textContent = text;
  el.status.style.color = isError ? "#b42318" : "#0f4b8a";
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function sanitizeFilePart(input) {
  return (input || "")
    .trim()
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 50);
}

function canonicalQuestion(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\b(please|kindly|required|optional|select|one|the|a|an)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function mergeLearnedQuestionBank(learnedQuestions = []) {
  const items = Array.isArray(learnedQuestions) ? learnedQuestions : [];
  if (!items.length) return 0;
  const stored = await chrome.storage.local.get({ profile: {} });
  const profile = stored.profile || {};
  const existing = Array.isArray(profile.questionBank) ? profile.questionBank : [];
  const merged = [...existing];
  const seen = new Set(existing.map((x) => `${canonicalQuestion(x?.question || "")}|${String(x?.answer || "").toLowerCase()}`));
  let added = 0;
  for (const item of items) {
    const question = String(item?.question || "").trim();
    const answer = String(item?.answer || "").trim();
    if (!question || !answer) continue;
    const key = `${canonicalQuestion(question)}|${answer.toLowerCase()}`;
    if (!canonicalQuestion(question) || seen.has(key)) continue;
    seen.add(key);
    merged.push({ question, answer });
    added += 1;
  }
  if (added > 0) {
    profile.questionBank = merged.slice(-400);
    await chrome.storage.local.set({ profile });
  }
  return added;
}

async function savePacketToDocuments(showStatus = true) {
  if (!state.currentJobId) {
    throw new Error("Analyze and generate documents first.");
  }
  if (!state.docs?.resume_pdf || !state.docs?.cover_letter_pdf) {
    throw new Error("Documents not generated yet. Click Generate tailored resume + cover letter first.");
  }
  const response = await callApi("/save_packet", "POST", { job_id: state.currentJobId });
  await chrome.storage.local.set({ lastSavedPacketFolder: response.folder });
  if (showStatus) {
    setStatus(`Saved packet to ${response.folder}`);
  }
  return response;
}

async function downloadGeneratedDoc(path, filename) {
  if (!path) throw new Error("Document path missing.");
  await chrome.runtime.sendMessage({
    type: "download_file",
    path,
    filename,
    saveAs: false,
  });
}

async function activeTab() {
  let tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let tab = tabs.find((t) => t && typeof t.id === "number");
  if (tab) return tab;

  tabs = await chrome.tabs.query({ active: true });
  tab = tabs.find((t) => t && typeof t.id === "number");
  if (tab) return tab;

  tabs = await chrome.tabs.query({});
  const validTabs = tabs.filter((t) => t && typeof t.id === "number");
  if (!validTabs.length) return null;
  validTabs.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0));
  return validTabs[0] || null;
}

function isInjectableUrl(url) {
  return !!url && /^https?:\/\//i.test(url);
}

async function sendTabMessageWithInject(tabId, tabUrl, message, options = {}) {
  if (tabUrl && !isInjectableUrl(tabUrl)) {
    throw new Error("Open a regular job webpage (http/https), not browser internal pages.");
  }
  const sendWithTimeout = (msgOptions = {}) =>
    Promise.race([
      chrome.tabs.sendMessage(tabId, message, msgOptions),
      new Promise((_, reject) => setTimeout(() => reject(new Error("Timed out waiting for page response.")), 12000)),
    ]);
  try {
    return await sendWithTimeout(options);
  } catch (err) {
    const msg = String(err?.message || err || "");
    if (!msg.includes("Receiving end does not exist") && !msg.includes("Timed out waiting for page response")) {
      throw err;
    }
    await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      files: ["content_script.js"],
    });
    return sendWithTimeout(options);
  }
}

async function extractFromPage() {
  const tab = await activeTab();
  if (!tab || !tab.id) throw new Error("No active tab available");
  state.currentTabId = tab.id;
  const response = await sendTabMessageWithInject(
    tab.id,
    tab.url,
    { type: "extract_job", requireTop: true },
    { frameId: 0 }
  );

  const extracted = response.jobText || "";
  const existing = (el.jobText.value || "").trim();
  if (extracted.length >= 300 || existing.length < 300) {
    el.jobText.value = extracted;
  }
  el.jobTitle.value = (response.pageTitle || "").split("|")[0]?.trim() || "";
  if (response.captchaDetected) {
    setStatus("CAPTCHA detected on page. Prefill assistance will be blocked.", true);
  } else {
    setStatus("Job text extracted. Review and edit before analysis.");
  }
}

function renderAnalysis(data) {
  state.currentJobId = data.job_id;
  state.currentTitle = data.title || el.jobTitle.value || "";
  state.currentCompany = data.company || el.companyHint.value || "";
  if (state.currentTitle && !looksLikePersonName(state.currentTitle)) {
    state.lastStableRoleTitle = state.currentTitle;
  }
  if (state.currentCompany && !looksLikePersonName(state.currentCompany)) {
    state.lastStableCompany = state.currentCompany;
  }
  chrome.storage.local.set({
    lastStableRoleTitle: state.lastStableRoleTitle,
    lastStableCompany: state.lastStableCompany,
  }).catch(() => {});
  state.complianceReady = !!data.compliance_ready;
  state.docs = null;

  el.summary.textContent = data.summary || "";
  el.fitScore.textContent = `${data.fit_score}/100`;
  clearNode(el.fitReasons);
  (data.fit_reasons || []).forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r;
    el.fitReasons.appendChild(li);
  });

  el.bulletIds.textContent = (data.suggested_bullets || []).join(", ") || "None";
  el.keywordCoverage.textContent = `${data.keyword_coverage_pct ?? 0}%`;
  el.matchedKeywords.textContent = (data.matched_keywords || []).join(", ") || "None";
  el.missingKeywords.textContent = (data.missing_keywords || []).join(", ") || "None";
  el.issueCard.classList.add("hidden");
  el.issueSummary.textContent = "";
  el.issueHowHelp.textContent = "";
  el.linkedinIssueBrief.textContent = "";
  clearNode(el.issueSources);
  clearNode(el.complianceNotes);
  (data.compliance_notes || []).forEach((c) => {
    const li = document.createElement("li");
    li.textContent = c;
    el.complianceNotes.appendChild(li);
  });

  el.results.classList.remove("hidden");
  el.generateBtn.disabled = !state.complianceReady;
  el.boostBtn.disabled = !state.complianceReady;
  el.markAppliedBtn.disabled = true;
  el.prefillBtn.disabled = false;
  el.downloads.classList.add("hidden");

  if (!state.complianceReady) {
    setStatus("Compliance blockers found in profile. Update options/profile before generating final docs.", true);
  } else {
    setStatus("Analysis complete. Generate docs after review.");
  }
}

function renderIssueBrief(issue) {
  const brief = issue || {};
  el.issueSummary.textContent = brief.issue_summary || brief.issue_title || "No recent issue brief available.";
  el.issueHowHelp.textContent = brief.how_candidate_can_help || "N/A";
  el.linkedinIssueBrief.textContent = brief.linkedin_outreach_note || "N/A";
  clearNode(el.issueSources);
  (brief.sources || []).forEach((s) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = s.url || "#";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = `${s.title || "Source"}${s.published_at ? ` (${String(s.published_at).slice(0, 10)})` : ""}`;
    li.appendChild(a);
    el.issueSources.appendChild(li);
  });
  el.issueCard.classList.remove("hidden");
}

function parseReferralContacts(text) {
  const rawLines = String(text || "")
    .split("\n")
    .map((x) => x.trim());
  const lines = [];
  let buffer = "";
  for (const line of rawLines) {
    if (!line) continue;
    buffer = buffer ? `${buffer} ${line}` : line;
    const pipes = (buffer.match(/\|/g) || []).length;
    if (pipes >= 3) {
      lines.push(buffer);
      buffer = "";
    }
  }
  if (buffer) lines.push(buffer);
  const contacts = [];
  for (const line of lines) {
    const parts = line.split("|").map((x) => x.trim());
    const [name = "", title = "", linkedin_url = "", email = ""] = parts;
    const cleanedEmail = /^none$/i.test(String(email || "").trim()) ? "" : String(email || "").trim();
    if (!name && !linkedin_url && !email) continue;
    contacts.push({ name, title, linkedin_url, email: cleanedEmail });
  }
  return contacts;
}

function scoreTargetContact(contact, roleTitle = "") {
  const title = String(contact?.title || "").toLowerCase();
  const context = String(contact?.context || "").toLowerCase();
  const role = String(roleTitle || "").toLowerCase();
  let score = 0;

  if (/recruit|talent|sourcer|staffing|people ops|hr\b/.test(title)) score += 40;
  if (/hiring manager|manager|director|head|lead|principal/.test(title)) score += 30;
  if (/data analyst|data science|data engineer|analytics|bi|sap/.test(title)) score += 20;
  if (role && title && role.split(/\s+/).some((t) => t.length > 3 && title.includes(t))) score += 15;
  if (/accenture/.test(context)) score += 12;
  if (/ltim|lti|ltimindtree/.test(context)) score += 12;
  if (/stevens institute|stevens\b/.test(context)) score += 12;
  if (/human resources|people partner/.test(context)) score += 8;
  return score;
}

function chooseTopTargetContacts(rawContacts, roleTitle, limit = 12) {
  const contacts = Array.isArray(rawContacts) ? rawContacts : [];
  const dedup = new Map();
  for (const c of contacts) {
    const key = String(c.linkedin_url || c.name || "").toLowerCase();
    if (!key) continue;
    if (!dedup.has(key)) dedup.set(key, c);
  }
  return Array.from(dedup.values())
    .map((c) => ({ ...c, _score: scoreTargetContact(c, roleTitle) }))
    .sort((a, b) => (b._score || 0) - (a._score || 0))
    .slice(0, limit);
}

function contactsToTextareaLines(contacts) {
  return (Array.isArray(contacts) ? contacts : [])
    .map((c) =>
      [
        String(c.name || "").trim(),
        String(c.title || "").trim(),
        String(c.linkedin_url || "").trim(),
        String(c.email || "").trim(),
      ].join(" | ")
    )
    .join("\n");
}

function buildContactDisplayName(contact) {
  const name = String(contact?.name || contact?.contact_name || "").trim();
  const title = String(contact?.title || contact?.contact_title || "").trim();
  const email = String(contact?.email || "").trim();
  const parts = [name || "Contact"];
  if (title) parts.push(title);
  if (email) parts.push(email);
  return parts.join(" | ");
}

function getUnifiedContactsForSelection() {
  const parsed = state.referralContactsCache.length
    ? state.referralContactsCache
    : parseReferralContacts(String(el.referralContacts?.value || ""));
  const drafts = Array.isArray(state.referralDrafts) ? state.referralDrafts : [];
  const byUrl = new Map();

  for (const c of parsed) {
    const url = String(c.linkedin_url || "").trim();
    const key = url || `${String(c.name || "").toLowerCase()}|${String(c.title || "").toLowerCase()}`;
    if (!key) continue;
    byUrl.set(key, { ...c });
  }
  for (const d of drafts) {
    const url = String(d.linkedin_url || "").trim();
    const key = url || `${String(d.contact_name || "").toLowerCase()}|${String(d.contact_title || "").toLowerCase()}`;
    if (!key) continue;
    if (!byUrl.has(key)) {
      byUrl.set(key, {
        name: d.contact_name || "",
        title: d.contact_title || "",
        linkedin_url: d.linkedin_url || "",
        email: d.email || "",
      });
      continue;
    }
    const existing = byUrl.get(key) || {};
    byUrl.set(key, {
      ...existing,
      name: existing.name || d.contact_name || "",
      title: existing.title || d.contact_title || "",
      linkedin_url: existing.linkedin_url || d.linkedin_url || "",
      email: existing.email || d.email || "",
    });
  }

  return Array.from(byUrl.values()).filter((c) => String(c.linkedin_url || "").trim());
}

function refreshReferralContactSelect() {
  const sel = el.referralContactSelect;
  if (!sel) return;
  const contacts = getUnifiedContactsForSelection();
  const previous = sel.value || "";
  while (sel.firstChild) sel.removeChild(sel.firstChild);
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a contact...";
  sel.appendChild(placeholder);
  contacts.forEach((c, idx) => {
    const opt = document.createElement("option");
    opt.value = String(c.linkedin_url || "").trim();
    opt.textContent = buildContactDisplayName(c);
    opt.dataset.index = String(idx);
    sel.appendChild(opt);
  });
  if (previous && Array.from(sel.options).some((o) => o.value === previous)) {
    sel.value = previous;
  }
}

function selectedContactOrFirst() {
  const contacts = getUnifiedContactsForSelection();
  const selectedUrl = String(el.referralContactSelect?.value || "").trim();
  if (selectedUrl) {
    const selected = contacts.find((c) => String(c.linkedin_url || "").trim() === selectedUrl);
    if (selected) return selected;
  }
  return contacts[0] || null;
}

function makeLinkedInNote(contact, profile) {
  const name = String(contact?.name || "there").split(" ")[0];
  const role = resolveOutreachRole(contact);
  const company = resolveOutreachCompany();
  const sender = String(profile?.fullName || "").trim();
  const context = `Hi ${name}, I applied for the ${role} role at ${company}.`;
  const personalization = "Your background stood out to me.";
  const softAsk = "If you’re open to it, I’d really appreciate a brief chat to learn from your experience.";
  const question = "Could you share a few tips on what the team values most?";
  const signoff = sender ? ` - ${sender}` : "";

  let note = `${context} ${personalization} ${softAsk} ${question}${signoff}`;
  if (note.length <= 280) return note;

  note = `${context} ${personalization} ${softAsk} ${question}`;
  if (note.length <= 280) return note;

  const shortRole = role.length > 54 ? `${role.slice(0, 51)}...` : role;
  const shortContext = `Hi ${name}, I applied for ${shortRole} at ${company}.`;
  note = `${shortContext} ${personalization} ${softAsk} ${question}`;
  return note.slice(0, 280);
}

function makeEmailDraft(contact, profile) {
  const contactName = String(contact?.name || "there");
  const firstName = contactName.split(" ")[0] || "there";
  const role = resolveOutreachRole(contact);
  const company = resolveOutreachCompany();
  const senderName = String(profile?.fullName || "Candidate").trim();
  const subject = `Application for ${role}`;
  const body = [
    `Hi ${firstName},`,
    "",
    `Hope you’re doing well. I recently applied for the ${role} role at ${company} and wanted to reach out.`,
    "",
    "I’ve spent the last 4+ years working in data science and analytics, mainly with Python, SQL, ML models, and data pipelines. Most of my work has been around turning raw data into practical insights and decisions for business teams.",
    "",
    "If you have a minute, I’d really appreciate any advice on what the team looks for most in candidates for this role.",
    "",
    "Thanks for your time.",
    `${senderName}`,
  ].join("\n");
  return { subject, body };
}

function looksLikePersonName(text) {
  const raw = String(text || "").trim();
  if (!raw) return false;
  const parts = raw.split(/\s+/).filter(Boolean);
  if (parts.length < 2 || parts.length > 4) return false;
  if (/\b(role|engineer|analyst|scientist|manager|intern|consultant|specialist|associate)\b/i.test(raw)) return false;
  return parts.every((p) => /^[A-Z][a-z'-]+$/.test(p));
}

function resolveOutreachRole(contact) {
  const contactName = String(contact?.name || "").trim().toLowerCase();
  const candidates = [
    String(state.currentTitle || "").trim(),
    String(el.jobTitle?.value || "").trim(),
    String(state.lastStableRoleTitle || "").trim(),
  ].filter(Boolean);
  for (const role of candidates) {
    const low = role.toLowerCase();
    if (contactName && low === contactName) continue;
    if (looksLikePersonName(role)) continue;
    return role;
  }
  return "this role";
}

function resolveOutreachCompany() {
  const candidates = [
    String(state.currentCompany || "").trim(),
    String(el.companyHint?.value || "").trim(),
    String(state.lastStableCompany || "").trim(),
  ].filter(Boolean);
  for (const c of candidates) {
    if (!looksLikePersonName(c)) return c;
  }
  return "your company";
}

function buildMailto(email, subject, body) {
  const safeEmail = String(email || "").trim();
  const qs = new URLSearchParams({
    subject: String(subject || ""),
    body: String(body || ""),
  }).toString();
  return `mailto:${encodeURIComponent(safeEmail)}?${qs}`;
}

function buildGmailComposeUrl(email, subject, body) {
  const params = new URLSearchParams({
    view: "cm",
    fs: "1",
    tf: "1",
    to: String(email || "").trim(),
    su: String(subject || ""),
    body: String(body || ""),
  });
  return `https://mail.google.com/mail/u/0/?${params.toString()}`;
}

async function copyText(text) {
  const value = String(text || "");
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function renderReferralDrafts() {
  const drafts = Array.isArray(state.referralDrafts) ? state.referralDrafts : [];
  clearNode(el.referralDrafts);
  if (!drafts.length) {
    el.referralDrafts.classList.add("hidden");
    return;
  }
  el.referralDrafts.classList.remove("hidden");
  drafts.forEach((d, idx) => {
    const card = document.createElement("div");
    card.className = "referral-item";

    const name = document.createElement("p");
    name.innerHTML = `<strong>${d.contact_name || "Contact"}${d.contact_title ? ` (${d.contact_title})` : ""}</strong>`;
    card.appendChild(name);

    const note = document.createElement("p");
    note.textContent = `LinkedIn note: ${d.linkedin_note || ""}`;
    card.appendChild(note);

    const followup = document.createElement("p");
    followup.textContent = `LinkedIn follow-up: ${d.linkedin_followup || ""}`;
    card.appendChild(followup);

    const subject = document.createElement("p");
    subject.textContent = `Email subject: ${d.email_subject || ""}`;
    card.appendChild(subject);

    const mini = document.createElement("div");
    mini.className = "mini-actions";

    const copyNote = document.createElement("button");
    copyNote.textContent = "Copy note";
    copyNote.onclick = async () => {
      const ok = await copyText(d.linkedin_note || "");
      setStatus(ok ? "LinkedIn note copied." : "Could not copy note. Copy manually.", !ok);
    };
    mini.appendChild(copyNote);

    const copyFollowup = document.createElement("button");
    copyFollowup.textContent = "Copy follow-up";
    copyFollowup.onclick = async () => {
      const ok = await copyText(d.linkedin_followup || "");
      setStatus(ok ? "LinkedIn follow-up copied." : "Could not copy follow-up. Copy manually.", !ok);
    };
    mini.appendChild(copyFollowup);

    if (d.linkedin_url) {
      const openLinkedIn = document.createElement("button");
      openLinkedIn.textContent = "Open profile";
      openLinkedIn.onclick = () => chrome.tabs.create({ url: d.linkedin_url });
      mini.appendChild(openLinkedIn);
    }

    if (d.email) {
      const openEmail = document.createElement("button");
      openEmail.textContent = "Open email";
      openEmail.onclick = () =>
        chrome.tabs.create({
          url: buildMailto(d.email, d.email_subject || "", d.email_body || ""),
        });
      mini.appendChild(openEmail);
    }

    card.appendChild(mini);
    el.referralDrafts.appendChild(card);
  });
}

async function callApi(path, method = "GET", body = null) {
  const response = await Promise.race([
    chrome.runtime.sendMessage({
      type: "api_request",
      path,
      method,
      body,
    }),
    new Promise((_, reject) => {
      const longRunning = new Set(["/analyze_job", "/generate_docs", "/referral_drafts", "/find_targets"]);
      const timeoutMs = longRunning.has(path) ? 95000 : 35000;
      setTimeout(() => reject(new Error(`Timed out waiting for ${path} response.`)), timeoutMs);
    }),
  ]);
  if (!response?.ok) throw new Error(response?.error || "API request failed");
  return response.data;
}

async function analyzeJob() {
  if (!el.jobText.value || el.jobText.value.length < 50) {
    await extractFromPage();
  }
  if (!el.jobText.value || el.jobText.value.length < 50) {
    const cached = await chrome.storage.local.get({ lastGoodJobText: "" });
    if (cached.lastGoodJobText && cached.lastGoodJobText.length >= 300) {
      el.jobText.value = cached.lastGoodJobText;
      setStatus("Using last saved job description because this page has limited text.");
    } else {
      throw new Error("Could not extract enough job text. Paste the full job description and try again.");
    }
  }
  const tab = await activeTab();
  const payload = {
    url: tab?.url || "",
    page_title: tab?.title || el.jobTitle.value || "",
    company_hint: el.companyHint.value || "",
    job_text: el.jobText.value,
  };
  const result = await callApi("/analyze_job", "POST", payload);
  if (el.jobText.value && el.jobText.value.length >= 300) {
    await chrome.storage.local.set({ lastGoodJobText: el.jobText.value });
  }
  return result;
}

async function analyzeEditedTextOnly() {
  const edited = String(el.jobText.value || "").trim();
  if (edited.length < 50) {
    throw new Error("Edited text is too short. Paste at least 50 characters from the job description.");
  }
  const tab = await activeTab();
  const payload = {
    url: tab?.url || "",
    page_title: tab?.title || el.jobTitle.value || "",
    company_hint: el.companyHint.value || "",
    job_text: edited,
  };
  const result = await callApi("/analyze_job", "POST", payload);
  if (edited.length >= 300) {
    await chrome.storage.local.set({ lastGoodJobText: edited });
  }
  return result;
}

async function fetchTextFile(path) {
  if (!path) return "";
  const response = await chrome.runtime.sendMessage({
    type: "fetch_text_file",
    path,
  });
  if (!response?.ok) return "";
  return response.text || "";
}

async function generateDocs(boostCoverage = false) {
  if (!state.currentJobId) throw new Error("Analyze a job first.");
  const confirmed = window.confirm(
    boostCoverage
      ? "Boost keyword coverage and regenerate documents now? This still uses factual profile data only."
      : "Generate final tailored documents now? This requires your explicit approval and uses your local profile facts only."
  );
  if (!confirmed) return null;

  return callApi("/generate_docs", "POST", {
    job_id: state.currentJobId,
    approve: true,
    boost_coverage: Boolean(boostCoverage),
  });
}

async function syncAnalyzedJob(result) {
  if (!result?.job_id) return null;
  try {
    const tab = await activeTab();
    return await callApi("/sync_job", "POST", {
      source_job_id: result.job_id,
      url: tab?.url || "",
      page_title: tab?.title || el.jobTitle.value || "",
      company_hint: el.companyHint.value || "",
      title: result.title || state.currentTitle || "",
      company: result.company || state.currentCompany || "",
      job_text: String(el.jobText?.value || "").trim(),
      summary: result.summary || "",
      fit_score: result.fit_score ?? null,
      fit_reasons: Array.isArray(result.fit_reasons) ? result.fit_reasons : [],
      tailoring_plan: Array.isArray(result.tailoring_plan) ? result.tailoring_plan : [],
      suggested_bullets: Array.isArray(result.suggested_bullets) ? result.suggested_bullets : [],
      suggested_project_ids: Array.isArray(result.suggested_project_ids) ? result.suggested_project_ids : [],
      matched_keywords: Array.isArray(result.matched_keywords) ? result.matched_keywords : [],
      missing_keywords: Array.isArray(result.missing_keywords) ? result.missing_keywords : [],
      keyword_coverage_pct: Number(result.keyword_coverage_pct || 0),
      compliance_ready: Boolean(result.compliance_ready),
      compliance_notes: Array.isArray(result.compliance_notes) ? result.compliance_notes : [],
      visibility: "public",
    });
  } catch (err) {
    console.warn("Job sync failed", err);
    return null;
  }
}

async function assistUpload(kind) {
  const tab = await activeTab();
  if (!tab || !tab.id) {
    throw new Error("No active tab available for upload.");
  }
  const result = await sendTabMessageWithInject(tab.id, tab.url, { type: "assist_upload", kind });
  if ((result.warnings || []).length > 0) {
    setStatus(result.warnings.join("; "), true);
  } else {
    setStatus(`Opened ${kind} file picker. Select the generated file from your configured Documents packet folder.`);
  }
}

function renderDownloads(result) {
  state.docs = result.files || null;
  if (!state.docs?.resume_pdf || !state.docs?.cover_letter_pdf) {
    el.downloads.classList.add("hidden");
    return;
  }

  el.downloads.classList.remove("hidden");
  el.downloadAllBtn.onclick = async () => {
    try {
      await savePacketToDocuments(true);
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };

  el.downloadPdfPairBtn.onclick = async () => {
    try {
      const { profile } = await chrome.storage.local.get({ profile: {} });
      const title = sanitizeFilePart(state.currentTitle || "JobRole");
      const company = sanitizeFilePart(state.currentCompany || "Company");
      const name = sanitizeFilePart(profile?.fullName || "Candidate");
      await downloadGeneratedDoc(state.docs?.resume_pdf, `${title}_${company}_${name}.pdf`);
      await downloadGeneratedDoc(state.docs?.cover_letter_pdf, `${title}_${company}_${name}_CoverLetter.pdf`);
      setStatus("Resume + cover letter PDF downloaded.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };

  el.downloadDocxPairBtn.onclick = async () => {
    try {
      const { profile } = await chrome.storage.local.get({ profile: {} });
      const title = sanitizeFilePart(state.currentTitle || "JobRole");
      const company = sanitizeFilePart(state.currentCompany || "Company");
      const name = sanitizeFilePart(profile?.fullName || "Candidate");
      await downloadGeneratedDoc(state.docs?.resume_docx, `${title}_${company}_${name}.docx`);
      await downloadGeneratedDoc(state.docs?.cover_letter_docx, `${title}_${company}_${name}_CoverLetter.docx`);
      setStatus("Resume + cover letter DOCX downloaded.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };

  el.uploadResumeBtn.onclick = async () => {
    try {
      await assistUpload("resume");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };
  el.uploadCoverBtn.onclick = async () => {
    try {
      await assistUpload("cover_letter");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };
}

async function refreshHistory() {
  clearNode(el.historyList);
  try {
    const jobs = await callApi("/jobs", "GET");
    await chrome.storage.local.set({ jobHistory: jobs });
    jobs.forEach((job) => {
      const li = document.createElement("li");
      li.textContent = `#${job.id} ${job.title} @ ${job.company} [${job.status}]`;
      el.historyList.appendChild(li);
    });
  } catch (err) {
    const cached = await chrome.storage.local.get({ jobHistory: [] });
    cached.jobHistory.forEach((job) => {
      const li = document.createElement("li");
      li.textContent = `#${job.id} ${job.title} @ ${job.company} [${job.status}]`;
      el.historyList.appendChild(li);
    });
  }
}

el.analyzeCurrentBtn.addEventListener("click", async () => {
  const runId = Date.now();
  state.analyzeRunId = runId;
  el.spinner.classList.remove("hidden");
  el.analyzeCurrentBtn.disabled = true;
  el.analyzeBtn.disabled = true;
  setStatus("Analyzing job...");
  const watchdog = setTimeout(() => {
    if (state.analyzeRunId !== runId) return;
    el.spinner.classList.add("hidden");
    el.analyzeCurrentBtn.disabled = false;
    el.analyzeBtn.disabled = false;
    setStatus("Analyze timed out in UI. Please click Analyze again.", true);
  }, 120000);
  try {
    await extractFromPage();
    const result = await analyzeJob();
    renderAnalysis(result);
    await syncAnalyzedJob(result);
    await refreshHistory();
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    clearTimeout(watchdog);
    el.spinner.classList.add("hidden");
    el.analyzeCurrentBtn.disabled = false;
    el.analyzeBtn.disabled = false;
    if (state.analyzeRunId === runId) state.analyzeRunId = 0;
  }
});

el.analyzeBtn.addEventListener("click", async () => {
  const runId = Date.now();
  state.analyzeRunId = runId;
  el.spinner.classList.remove("hidden");
  el.analyzeCurrentBtn.disabled = true;
  el.analyzeBtn.disabled = true;
  setStatus("Analyzing edited text...");
  const watchdog = setTimeout(() => {
    if (state.analyzeRunId !== runId) return;
    el.spinner.classList.add("hidden");
    el.analyzeCurrentBtn.disabled = false;
    el.analyzeBtn.disabled = false;
    setStatus("Analyze timed out in UI. Please click Analyze again.", true);
  }, 120000);
  try {
    const result = await analyzeEditedTextOnly();
    renderAnalysis(result);
    await syncAnalyzedJob(result);
    await refreshHistory();
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    clearTimeout(watchdog);
    el.spinner.classList.add("hidden");
    el.analyzeCurrentBtn.disabled = false;
    el.analyzeBtn.disabled = false;
    if (state.analyzeRunId === runId) state.analyzeRunId = 0;
  }
});

el.generateBtn.addEventListener("click", async () => {
  try {
    const result = await generateDocs();
    if (!result) return;
    if (!result.compliance_passed) {
      setStatus(`Compliance blocked doc generation: ${result.compliance_issues.join("; ")}`, true);
      return;
    }
    renderDownloads(result);
    let savedFolder = "";
    try {
      const packet = await savePacketToDocuments(false);
      savedFolder = packet?.folder || "";
    } catch {
      // Keep docs usable even if folder save fails.
    }
    el.keywordCoverage.textContent = `${result.keyword_coverage_pct ?? 0}%`;
    el.matchedKeywords.textContent = (result.matched_keywords || []).join(", ") || "None";
    el.missingKeywords.textContent = (result.missing_keywords || []).join(", ") || "None";
    el.boostBtn.disabled = false;
    el.markAppliedBtn.disabled = false;
    setStatus(
      savedFolder
        ? `Documents generated. Saved to ${savedFolder}. Auto-fill is available.`
        : "Documents generated. Auto-fill is available."
    );
    await refreshHistory();
  } catch (err) {
    setStatus(err.message, true);
  }
});

el.boostBtn.addEventListener("click", async () => {
  try {
    const result = await generateDocs(true);
    if (!result) return;
    if (!result.compliance_passed) {
      setStatus(`Compliance blocked doc generation: ${result.compliance_issues.join("; ")}`, true);
      return;
    }
    renderDownloads(result);
    let savedFolder = "";
    try {
      const packet = await savePacketToDocuments(false);
      savedFolder = packet?.folder || "";
    } catch {
      // Keep docs usable even if folder save fails.
    }
    el.keywordCoverage.textContent = `${result.keyword_coverage_pct ?? 0}%`;
    el.matchedKeywords.textContent = (result.matched_keywords || []).join(", ") || "None";
    el.missingKeywords.textContent = (result.missing_keywords || []).join(", ") || "None";
    el.markAppliedBtn.disabled = false;
    setStatus(savedFolder ? `Boost completed. Saved to ${savedFolder}.` : "Boost coverage regeneration completed.");
    await refreshHistory();
  } catch (err) {
    setStatus(err.message, true);
  }
});

el.checkIssueBtn.addEventListener("click", async () => {
  try {
    if (!state.currentJobId) throw new Error("Analyze a job first.");
    setStatus("Fetching latest company issue brief...");
    const resp = await callApi("/company_issue", "POST", { job_id: state.currentJobId });
    renderIssueBrief(resp.issue_brief || {});
    setStatus("Issue brief ready. Use it for LinkedIn outreach.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
});

el.markAppliedBtn.addEventListener("click", async () => {
  try {
    if (!state.currentJobId) throw new Error("Analyze a job first.");
    await callApi("/mark_applied", "POST", { job_id: state.currentJobId, notes: "" });
    setStatus("Marked as applied. You can now export the applied jobs CSV.");
    await refreshHistory();
  } catch (err) {
    setStatus(err.message, true);
  }
});

el.exportAppliedBtn.addEventListener("click", async () => {
  try {
    await chrome.runtime.sendMessage({
      type: "download_file",
      path: "/export/applied.csv",
      filename: "jobapply-applied-jobs.csv",
      saveAs: false,
    });
    setStatus("Started CSV download for applied jobs.");
  } catch (err) {
    setStatus(err.message, true);
  }
});

el.findTargetsBtn.addEventListener("click", async () => {
  try {
    if (!state.currentJobId) throw new Error("Analyze a job first.");
    setStatus("Finding targets from job/company...");
    let contacts = [];
    const apiResp = await callApi("/find_targets", "POST", { job_id: state.currentJobId });
    contacts = chooseTopTargetContacts(apiResp.contacts || [], state.currentTitle || el.jobTitle.value || "");
    const apiWarnings = Array.isArray(apiResp.warnings) ? apiResp.warnings : [];

    // Optional fallback: if user is on LinkedIn page and API discovery is thin, enrich from visible page.
    if (contacts.length < 3) {
      const tab = await activeTab();
      if (tab?.id && /linkedin\.com/i.test(String(tab.url || ""))) {
        const pageResp = await sendTabMessageWithInject(tab.id, tab.url, { type: "extract_linkedin_contacts" });
        const pageContacts = chooseTopTargetContacts(pageResp.contacts || [], state.currentTitle || el.jobTitle.value || "");
        const byUrl = new Map();
        for (const c of [...contacts, ...pageContacts]) {
          const key = String(c.linkedin_url || c.name || "").toLowerCase();
          if (!key || byUrl.has(key)) continue;
          byUrl.set(key, c);
        }
        contacts = Array.from(byUrl.values()).slice(0, 12);
      }
    }

    if (!contacts.length) {
      throw new Error(apiWarnings[0] || "No target contacts found for this company.");
    }
    state.referralContactsCache = contacts;
    const lines = contactsToTextareaLines(contacts);
    el.referralContacts.value = lines;
    await chrome.storage.local.set({ referralContactsText: lines });
    refreshReferralContactSelect();
    const alumniHits = contacts.filter((c) => /stevens institute|stevens\b/i.test(`${String(c.context || "")} ${String((c.evidence || []).join(" "))}`)).length;
    const expHits = contacts.filter((c) => /accenture|ltim|lti|ltimindtree/i.test(`${String(c.context || "")} ${String((c.evidence || []).join(" "))}`)).length;
    setStatus(
      `Found ${contacts.length} target contacts for outreach. Shared background hits: ${expHits} ex-Accenture/LTIM, ${alumniHits} Stevens.`,
    );
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
});

el.generateReferralBtn.addEventListener("click", async () => {
  try {
    const raw = String(el.referralContacts.value || "").trim();
    const contacts = parseReferralContacts(raw);
    if (contacts.length) {
      state.referralContactsCache = contacts;
      await chrome.storage.local.set({ referralContactsText: raw });
    }
    refreshReferralContactSelect();
    const chosen = selectedContactOrFirst();
    if (!chosen) throw new Error("Add contacts first, then select one from dropdown.");
    const { profile } = await chrome.storage.local.get({ profile: {} });
    const note = makeLinkedInNote(chosen, profile || {});
    state.referralDrafts = [
      {
        contact_name: chosen.name || "",
        contact_title: chosen.title || "",
        linkedin_url: chosen.linkedin_url || "",
        email: chosen.email || "",
        linkedin_note: note,
        linkedin_followup: `Hi ${String(chosen.name || "").split(" ")[0] || "there"}, following up on my application for ${state.currentTitle || el.jobTitle.value || "the role"}. If possible, I’d really appreciate any referral guidance.`,
        email_subject: "",
        email_body: "",
      },
    ];
    refreshReferralContactSelect();
    renderReferralDrafts();
    setStatus("Connection note generated in the profile card below. Use Copy note / Copy follow-up.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
});

el.openProfilesBtn.addEventListener("click", async () => {
  try {
    refreshReferralContactSelect();
    const selected = String(el.referralContactSelect?.value || "").trim();
    if (!/^https?:\/\//i.test(selected)) {
      throw new Error("Select one contact from the dropdown first.");
    }
    await chrome.tabs.create({ url: selected });
    setStatus("Opened selected LinkedIn profile.");
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
});

el.openEmailDraftsBtn.addEventListener("click", async () => {
  try {
    const raw = String(el.referralContacts.value || "").trim();
    const contacts = parseReferralContacts(raw);
    if (contacts.length) state.referralContactsCache = contacts;
    refreshReferralContactSelect();
    const chosen = selectedContactOrFirst();
    if (!chosen) throw new Error("Add contacts first, then select one from dropdown.");
    const { profile } = await chrome.storage.local.get({ profile: {} });
    const draft = makeEmailDraft(chosen, profile || {});
    const emailText = `Subject: ${draft.subject}\n\n${draft.body}`;
    if (el.referralOutput) {
      el.referralOutput.value = emailText;
    }
    const toEmail = String(chosen.email || "").trim();
    if (toEmail) {
      await chrome.tabs.create({
        url: buildGmailComposeUrl(toEmail, draft.subject, draft.body),
      });
    }
    state.referralDrafts = [
      {
        contact_name: chosen.name || "",
        contact_title: chosen.title || "",
        linkedin_url: chosen.linkedin_url || "",
        email: chosen.email || "",
        linkedin_note: "",
        linkedin_followup: "",
        email_subject: draft.subject,
        email_body: draft.body,
      },
    ];
    renderReferralDrafts();
    setStatus(
      toEmail
        ? "Email draft generated and Gmail compose opened with recipient, subject, and body."
        : "Email draft generated. Recipient email missing for selected contact."
    );
  } catch (err) {
    setStatus(err.message || String(err), true);
  }
});

el.prefillBtn.addEventListener("click", async () => {
  try {
    const { profile } = await chrome.storage.local.get({ profile: {} });
    const tab = await activeTab();
    if (!tab || !tab.id) {
      throw new Error("No active tab available for prefill.");
    }
    const coverLetterText = await fetchTextFile(state.docs?.cover_letter_txt);
    const result = await sendTabMessageWithInject(tab.id, tab.url, {
      type: "prefill_form",
      profile,
      coverLetterText,
      aiFieldMode: Boolean(el.aiFieldMode?.checked),
      forceRefill: true,
      assistUploads: true,
      fileHints: {
        resume: state.docs?.resume_pdf ? "Generated Resume PDF" : "",
        coverLetter: state.docs?.cover_letter_pdf ? "Generated Cover Letter PDF" : "",
      },
    });
    const learnedCount = await mergeLearnedQuestionBank(result.learnedQuestions || []);
    if ((result.warnings || []).length > 0) {
      setStatus(
        `Prefill finished with warnings: ${result.warnings.join("; ")}${learnedCount > 0 ? ` Learned ${learnedCount} Q&A entries.` : ""}`,
        true
      );
    } else if ((result.filledCount || 0) === 0) {
      setStatus(
        "Prefill found no matching editable fields on this page. Open the actual application form step and retry.",
        true
      );
    } else {
      setStatus(
        `Prefill complete. Filled ${result.filledCount} fields. Submission remains manual.${learnedCount > 0 ? ` Learned ${learnedCount} Q&A entries.` : ""}`
      );
    }
  } catch (err) {
    setStatus(err.message, true);
  }
});

(async () => {
  const cached = await chrome.storage.local.get({
    referralContactsText: "",
    lastStableRoleTitle: "",
    lastStableCompany: "",
  });
  state.lastStableRoleTitle = String(cached.lastStableRoleTitle || "").trim();
  state.lastStableCompany = String(cached.lastStableCompany || "").trim();
  if (el.referralContacts) {
    el.referralContacts.value = cached.referralContactsText || "";
    el.referralContacts.addEventListener("input", async () => {
      await chrome.storage.local.set({ referralContactsText: String(el.referralContacts.value || "") });
      refreshReferralContactSelect();
    });
    refreshReferralContactSelect();
  }
  await refreshHistory();
  try {
    await extractFromPage();
  } catch {
    setStatus("Open a job page and click Analyze now.");
  }
})();
