const state = {
  currentTabId: null,
  currentJobId: null,
  currentTitle: "",
  currentCompany: "",
  currentLocation: "",
  docs: null,
  complianceReady: false,
  analyzeRunId: 0,
  referralDrafts: [],
  referralContactsCache: [],
  lastStableRoleTitle: "",
  lastStableCompany: "",
  analyzedFingerprint: "",
};

const el = {
  analyzeCurrentBtn: document.getElementById("analyzeCurrentBtn"),
  openTrackerBtn: document.getElementById("openTrackerBtn"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  generateBtn: document.getElementById("generateBtn"),
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
  networkMatches: document.getElementById("networkMatches"),
  networkMatchGroups: document.getElementById("networkMatchGroups"),
  prefillBtn: document.getElementById("prefillBtn"),
  aiFieldMode: document.getElementById("aiFieldMode"),
  jobTitle: document.getElementById("jobTitle"),
  companyHint: document.getElementById("companyHint"),
  jobText: document.getElementById("jobText"),
  spinner: document.getElementById("spinner"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  analysisRole: document.getElementById("analysisRole"),
  analysisCompany: document.getElementById("analysisCompany"),
  analysisLocation: document.getElementById("analysisLocation"),
  summary: document.getElementById("summary"),
  fitScore: document.getElementById("fitScore"),
  tailoredFitScore: document.getElementById("tailoredFitScore"),
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
  downloadDocxPairBtn: document.getElementById("downloadDocxPairBtn"),
  downloadPdfPairBtn: document.getElementById("downloadPdfPairBtn"),
  historyList: document.getElementById("historyList"),
  openaiApiKeyInline: document.getElementById("openaiApiKeyInline"),
  rememberOpenAiKeyInline: document.getElementById("rememberOpenAiKeyInline"),
  saveOpenAiKeyInlineBtn: document.getElementById("saveOpenAiKeyInlineBtn"),
  testOpenAiKeyInlineBtn: document.getElementById("testOpenAiKeyInlineBtn"),
  removeOpenAiKeyInlineBtn: document.getElementById("removeOpenAiKeyInlineBtn"),
  openAiKeyInlineStatus: document.getElementById("openAiKeyInlineStatus"),
};

function setStatus(msg, isError = false) {
  let text = msg || "";
  if (isError && /failed to fetch/i.test(String(text))) {
    text = "Cannot reach the JobApply Copilot API. Check the extension Options page and your production connection.";
  }
  if (!el.status) return;
  el.status.textContent = text;
  el.status.style.color = isError ? "#b42318" : "#0f4b8a";
}

function setInlineKeyStatus(message, isError = false) {
  if (!el.openAiKeyInlineStatus) return;
  el.openAiKeyInlineStatus.textContent = message || "";
  el.openAiKeyInlineStatus.style.color = isError ? "#b42318" : "#0f4b8a";
}

async function loadInlineApiKeyState() {
  if (!el.openaiApiKeyInline) return;
  const localStored = await chrome.storage.local.get({ openaiApiKey: "", rememberOpenAiKey: false });
  const sessionStored = await chrome.storage.session?.get({ openaiApiKey: "" }).catch(() => ({ openaiApiKey: "" })) || { openaiApiKey: "" };
  const key = sessionStored.openaiApiKey || localStored.openaiApiKey || "";
  el.openaiApiKeyInline.value = key;
  if (el.rememberOpenAiKeyInline) {
    el.rememberOpenAiKeyInline.checked = Boolean(localStored.rememberOpenAiKey);
  }
  setInlineKeyStatus(key ? "Extension API key loaded." : "No extension API key saved. Generation will use template fallback unless server fallback is enabled.");
}

async function saveInlineApiKeyState() {
  if (!el.openaiApiKeyInline) return;
  const key = String(el.openaiApiKeyInline.value || "").trim();
  const remember = Boolean(el.rememberOpenAiKeyInline?.checked);
  if (remember) {
    await chrome.storage.local.set({ openaiApiKey: key, rememberOpenAiKey: true });
    await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  } else {
    await chrome.storage.local.set({ openaiApiKey: "", rememberOpenAiKey: false });
    await chrome.storage.session?.set({ openaiApiKey: key }).catch(() => {});
  }
  setInlineKeyStatus(key ? "Saved for extension requests." : "No key saved. Generation will use fallback.");
}

async function removeInlineApiKeyState() {
  if (el.openaiApiKeyInline) el.openaiApiKeyInline.value = "";
  if (el.rememberOpenAiKeyInline) el.rememberOpenAiKeyInline.checked = false;
  await chrome.storage.local.set({ openaiApiKey: "", rememberOpenAiKey: false });
  await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  setInlineKeyStatus("API key removed from the extension.");
}

async function testInlineApiKeyState() {
  if (!el.openaiApiKeyInline) return;
  await saveInlineApiKeyState();
  const key = String(el.openaiApiKeyInline.value || "").trim();
  if (!key) {
    setInlineKeyStatus("Paste an API key before testing.", true);
    return;
  }
  try {
    const result = await callApi("/ai/test_key", "POST", {});
    setInlineKeyStatus(result.message || "API key authenticated successfully.");
  } catch (error) {
    setInlineKeyStatus(error?.message || "API key test failed.", true);
  }
}

async function openApplicationTracker() {
  const stored = await chrome.storage.local.get({
    websiteUrl: "https://jobapply-copilot-web.onrender.com/app/jobs",
  });
  const rawUrl = String(stored.websiteUrl || "https://jobapply-copilot-web.onrender.com/app/jobs").trim();
  try {
    const url = new URL(rawUrl);
    if (!["http:", "https:"].includes(url.protocol)) {
      throw new Error("Unsupported tracker URL protocol.");
    }
    setStatus(`Opening tracker: ${url.toString()}`);
    const created = await chrome.tabs.create({ url: url.toString(), active: true });
    if (!created?.id) {
      throw new Error("Chrome did not return a new tab.");
    }
  } catch (error) {
    setStatus(
      `Could not open application tracker. Start the web app and check the tracker URL in Options. ${error?.message || ""}`,
      true
    );
  }
}

function clearNode(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

function setText(node, value) {
  if (node) node.textContent = value;
}

function appendListItem(listNode, value) {
  if (!listNode) return;
  const li = document.createElement("li");
  li.textContent = value;
  listNode.appendChild(li);
}

function sanitizeFilePart(input) {
  return (input || "")
    .trim()
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 50);
}

function normalizeFingerprintPart(input) {
  return String(input || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function visibleJobFingerprint() {
  const title = cleanRoleForFilename(String(el.jobTitle?.value || "").trim());
  const company = String(el.companyHint?.value || "").trim();
  const text = cleanJobDescriptionForDisplay(String(el.jobText?.value || "")).slice(0, 600);
  return [
    normalizeFingerprintPart(title),
    normalizeFingerprintPart(company),
    normalizeFingerprintPart(text),
  ].join("|");
}

function resetGeneratedDocs(reason = "") {
  state.docs = null;
  if (el.downloads) el.downloads.classList.add("hidden");
  if (el.markAppliedBtn) el.markAppliedBtn.disabled = true;
  if (el.prefillBtn) el.prefillBtn.disabled = true;
  if (el.checkIssueBtn) el.checkIssueBtn.disabled = true;
  if (el.findTargetsBtn) el.findTargetsBtn.disabled = true;
  if (reason) setStatus(reason);
}

function cleanRoleForFilename(input) {
  return String(input || "")
    .trim()
    .replace(/\s+/g, " ")
    .replace(/^(?:job\s+)?application\s+for\s+/i, "")
    .replace(/\s+at\s+[A-Z][A-Za-z0-9&.,'()\- ]{1,80}$/i, "")
    .replace(/\s+job\s+in\s+.+$/i, "")
    .replace(/\s+(?:-|–|—)\s+[A-Z][A-Za-z .'-]+,\s*(?:[A-Z]{2}|[A-Z][A-Za-z .'-]+)$/i, "")
    .replace(/\s+in\s+[A-Z][A-Za-z .'-]+,\s*(?:\d{5}|[A-Z]{2})(?:\b.*)?$/, "")
    .replace(/\s+in\s+[A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+$/, "")
    .replace(/\s+\(?(remote|hybrid|onsite|on-site)\)?$/i, "")
    .trim();
}

function cleanJobDescriptionForDisplay(input) {
  const container = document.createElement("div");
  container.innerHTML = String(input || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|li|h[1-6])>/gi, "\n");
  const text = (container.innerText || container.textContent || String(input || ""))
    .replace(/\r/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ");
  const noise = [
    /^(req|job|requisition)\s*id\s*:?\s*$/i,
    /^(req|job|requisition)\s*id\s*:?\s*[a-z]{0,5}\d+$/i,
    /^[a-z]{1,5}\d{4,}\s+[a-z][a-z0-9 ,&/()#+.-]{0,80}$/i,
    /^share via (email|facebook|linkedin|twitter)$/i,
    /^apply now$/i,
    /^save job$/i,
    /^job details$/i,
    /^similar jobs$/i,
  ];
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !noise.some((pattern) => pattern.test(line)))
    .map((line) => line.replace(/^●\s*/, "- "));
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

function looksLikeBadJobTitle(text) {
  const raw = String(text || "").trim().toLowerCase();
  return !raw || /^(view more jobs|similar jobs|see more jobs|apply now|job info|more information|about us)$/.test(raw);
}

function cleanTitleFromPageTitle(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  const first = raw.split(/\s+[|–—-]\s+/)[0]?.trim() || raw;
  return first.replace(/\s+(careers?|jobs?)$/i, "").trim();
}

function resolveDownloadTitle() {
  const candidates = [
    cleanTitleFromPageTitle(String(el.jobTitle?.value || "").trim()),
    String(el.jobTitle?.value || "").trim(),
    String(state.currentTitle || "").trim(),
    String(state.lastStableRoleTitle || "").trim(),
  ].filter(Boolean);
  for (const candidate of candidates) {
    const cleaned = cleanRoleForFilename(candidate);
    if (!looksLikeBadJobTitle(cleaned) && !looksLikePersonName(cleaned)) return cleaned;
  }
  return "JobRole";
}

function resolveDownloadCompany() {
  const candidates = [
    String(el.companyHint?.value || "").trim(),
    inferCompanyFromText(String(el.jobTitle?.value || "").trim()),
    String(state.currentCompany || "").trim(),
    String(state.lastStableCompany || "").trim(),
  ].filter(Boolean);
  for (const candidate of candidates) {
    const low = candidate.toLowerCase();
    if (low && !["detected or edit manually", "unknown company", "company"].includes(low) && !looksLikePersonName(candidate)) {
      return candidate;
    }
  }
  return "Company";
}

function inferCompanyFromText(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  const patterns = [
    /\bat\s+([A-Z][A-Za-z0-9&.,'()\- ]{1,80})$/,
    /^(.+?)\s+[|@-]\s+([A-Z][A-Za-z0-9&.,'()\- ]{1,80})$/,
  ];
  for (const pattern of patterns) {
    const match = raw.match(pattern);
    if (match) {
      const candidate = String(match[match.length - 1] || "").trim();
      if (candidate && !looksLikePersonName(candidate)) return candidate;
    }
  }
  return "";
}

function companyFromContact(contact) {
  const title = String(contact?.title || contact?.contact_title || "").trim();
  const linkedinUrl = String(contact?.linkedin_url || "").trim();
  const patterns = [
    /\bat\s+([A-Z][A-Za-z0-9&.,'()\- ]{1,80})/i,
    /@\s*([A-Z][A-Za-z0-9&.,'()\- ]{1,80})/i,
  ];
  for (const pattern of patterns) {
    const match = title.match(pattern);
    if (match) {
      const candidate = String(match[1] || "").trim().replace(/\s+hiring.*$/i, "");
      if (candidate && !looksLikePersonName(candidate)) return candidate;
    }
  }
  if (/paloalto/i.test(linkedinUrl) || /palo alto/i.test(title)) return "Palo Alto Networks";
  if (/jpmorgan|jp morgan/i.test(linkedinUrl) || /jpmorgan|jp morgan/i.test(title)) return "JPMorgan";
  return "";
}

function deriveCurrentRoleCompanyContext() {
  const visibleTitle = String(el.jobTitle?.value || "").trim();
  const visibleCompany = String(el.companyHint?.value || "").trim();
  const inferredCompany = inferCompanyFromText(visibleTitle);
  const roleCandidates = [
    visibleTitle,
    String(state.currentTitle || "").trim(),
    String(state.lastStableRoleTitle || "").trim(),
  ].filter(Boolean);
  const companyCandidates = [
    visibleCompany,
    inferredCompany,
    String(state.currentCompany || "").trim(),
    String(state.lastStableCompany || "").trim(),
  ].filter(Boolean);

  let role = "this role";
  for (const candidate of roleCandidates) {
    if (!looksLikePersonName(candidate)) {
      role = candidate;
      break;
    }
  }

  let company = "your company";
  for (const candidate of companyCandidates) {
    if (!looksLikePersonName(candidate)) {
      company = candidate;
      break;
    }
  }

  return { role, company };
}

function deriveOutreachContextForContact(contact) {
  const base = deriveCurrentRoleCompanyContext();
  const contactCompany = companyFromContact(contact);
  let role = base.role;
  let company = base.company;

  if (contactCompany) {
    const currentCompanyLower = String(company || "").toLowerCase();
    const contactCompanyLower = String(contactCompany || "").toLowerCase();
    if (!currentCompanyLower || currentCompanyLower !== contactCompanyLower) {
      company = contactCompany;
    }
  }

  if (contactCompany && state.currentCompany) {
    const staleCompany = String(state.currentCompany || "").trim().toLowerCase();
    const selectedCompany = String(contactCompany || "").trim().toLowerCase();
    if (staleCompany && selectedCompany && staleCompany !== selectedCompany) {
      const visibleRole = String(el.jobTitle?.value || "").trim();
      if (!visibleRole || looksLikePersonName(visibleRole)) {
        role = "the role";
      }
    }
  }

  return { role, company };
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

  const extracted = cleanJobDescriptionForDisplay(response.jobText || "");
  const existing = (el.jobText.value || "").trim();
  if (extracted.length >= 300 || existing.length < 300) {
    el.jobText.value = extracted;
  }
  el.jobTitle.value = cleanRoleForFilename(response.jobTitle || (response.pageTitle || "").split("|")[0]?.trim() || "");
  if (response.company) {
    el.companyHint.value = String(response.company || "").trim();
  } else if (!String(el.companyHint.value || "").trim()) {
    const inferredCompany = inferCompanyFromText(response.pageTitle || "");
    if (inferredCompany) {
      el.companyHint.value = inferredCompany;
    }
  }
  if (response.captchaDetected) {
    setStatus("CAPTCHA detected on page. Prefill assistance will be blocked.", true);
  } else {
    setStatus("Job text extracted. Review and edit before analysis.");
  }
  state.currentJobId = null;
  state.analyzedFingerprint = "";
  resetGeneratedDocs();
}

function renderAnalysis(data) {
  state.currentJobId = data.job_id;
  state.currentTitle = data.title || el.jobTitle.value || "";
  state.currentCompany = data.company || el.companyHint.value || "";
  state.currentLocation = data.location || "";
  if (state.currentTitle && !looksLikeBadJobTitle(state.currentTitle)) {
    el.jobTitle.value = cleanRoleForFilename(state.currentTitle);
  }
  if (state.currentCompany) {
    el.companyHint.value = state.currentCompany;
  }
  el.jobText.value = cleanJobDescriptionForDisplay(el.jobText.value || "");
  state.analyzedFingerprint = visibleJobFingerprint();
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

  setText(el.analysisRole, state.currentTitle || "Review manually");
  setText(el.analysisCompany, state.currentCompany || "Review manually");
  setText(el.analysisLocation, state.currentLocation || "Not detected");
  setText(
    el.summary,
    state.complianceReady
      ? "Job details captured. Review the role/company/location, then generate documents when you are ready."
      : "Job details captured, but profile/compliance notes need attention before document generation."
  );
  setText(el.fitScore, `${data.fit_score}/100`);
  clearNode(el.fitReasons);
  (data.fit_reasons || []).forEach((r) => {
    appendListItem(el.fitReasons, r);
  });

  setText(el.bulletIds, (data.suggested_bullets || []).join(", ") || "None");
  setText(el.keywordCoverage, `${data.keyword_coverage_pct ?? 0}%`);
  setText(el.matchedKeywords, (data.matched_keywords || []).join(", ") || "None");
  setText(el.missingKeywords, (data.missing_keywords || []).join(", ") || "None");
  if (el.issueCard) el.issueCard.classList.add("hidden");
  setText(el.issueSummary, "");
  setText(el.issueHowHelp, "");
  setText(el.linkedinIssueBrief, "");
  clearNode(el.issueSources);
  clearNode(el.complianceNotes);
  (data.compliance_notes || []).forEach((c) => {
    appendListItem(el.complianceNotes, c);
  });

  if (el.results) el.results.classList.remove("hidden");
  if (el.generateBtn) el.generateBtn.disabled = !state.complianceReady;
  if (el.markAppliedBtn) el.markAppliedBtn.disabled = !state.currentJobId;
  if (el.prefillBtn) el.prefillBtn.disabled = false;
  if (el.checkIssueBtn) el.checkIssueBtn.disabled = !state.currentJobId;
  if (el.findTargetsBtn) el.findTargetsBtn.disabled = !state.currentJobId;
  if (el.downloads) el.downloads.classList.add("hidden");

  if (!state.complianceReady) {
    setStatus(
      "Compliance blockers prevent document generation, but you can still mark the job applied if you used an existing resume.",
      true
    );
  } else {
    const aiLabel = aiSourceLabel(data);
    const warning = (data.generation_warnings || [])[0] || "";
    setStatus(`Analysis complete. ${aiLabel}${warning ? ` ${warning}` : ""}`);
  }
}

function aiSourceLabel(data) {
  if (data?.ai_assisted && data?.ai_key_source === "byok") return "AI: using your API key.";
  if (data?.ai_assisted && data?.ai_key_source === "server") return "AI: using server key.";
  if (data?.ai_assisted) return "AI-assisted.";
  return "Template/heuristic fallback.";
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

function contactKey(contact) {
  return String(contact?.linkedin_url || "").trim().toLowerCase()
    || `${String(contact?.name || contact?.contact_name || "").trim().toLowerCase()}|${String(contact?.title || contact?.contact_title || "").trim().toLowerCase()}`;
}

function mergeContactsPreservingContext(existingContacts, editedContacts) {
  const existing = new Map((existingContacts || []).map((contact) => [contactKey(contact), contact]));
  return (editedContacts || []).map((contact) => {
    const previous = existing.get(contactKey(contact)) || {};
    return {
      ...previous,
      ...contact,
      relationship_type: previous.relationship_type || contact.relationship_type || "beyond_network",
      shared_context: previous.shared_context || contact.shared_context || "",
      evidence: previous.evidence || contact.evidence || [],
    };
  });
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
  if (contact?.relationship_type === "previous_company") score += 20;
  if (contact?.relationship_type === "school") score += 18;
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

function renderNetworkMatches(contacts) {
  if (!el.networkMatches || !el.networkMatchGroups) return;
  clearNode(el.networkMatchGroups);
  const groups = [
    { key: "previous_company", title: "From Your Previous Company", className: "previous-company" },
    { key: "school", title: "From Your School", className: "school" },
    { key: "beyond_network", title: "Beyond Your Network", className: "beyond-network" },
  ];
  for (const group of groups) {
    const matches = (contacts || []).filter((contact) => (contact.relationship_type || "beyond_network") === group.key);
    if (!matches.length) continue;
    const card = document.createElement("div");
    card.className = `network-group ${group.className}`;
    const header = document.createElement("div");
    header.className = "network-group-header";
    const title = document.createElement("strong");
    title.textContent = group.title;
    const count = document.createElement("span");
    count.className = "network-count";
    count.textContent = `${matches.length} found`;
    header.append(title, count);
    card.appendChild(header);

    matches.slice(0, 5).forEach((contact) => {
      const row = document.createElement("div");
      row.className = "network-contact";
      const avatar = document.createElement("span");
      avatar.className = "network-avatar";
      avatar.textContent = String(contact.name || "?").trim().charAt(0).toUpperCase() || "?";
      const copy = document.createElement("div");
      copy.className = "network-contact-copy";
      const name = document.createElement("strong");
      name.textContent = contact.name || "LinkedIn contact";
      const context = document.createElement("span");
      context.textContent = contact.shared_context
        ? `${contact.title || "Contact"} · Shared: ${contact.shared_context}`
        : (contact.title || "Potential company contact");
      copy.append(name, context);
      const select = document.createElement("button");
      select.type = "button";
      select.className = "secondary-button";
      select.textContent = "Use";
      select.addEventListener("click", () => {
        if (el.referralContactSelect) el.referralContactSelect.value = String(contact.linkedin_url || "").trim();
        setStatus(`${contact.name || "Contact"} selected for LinkedIn and email drafts.`);
      });
      row.append(avatar, copy, select);
      card.appendChild(row);
    });
    el.networkMatchGroups.appendChild(card);
  }
  el.networkMatches.classList.toggle("hidden", !el.networkMatchGroups.childElementCount);
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
  const { role, company } = deriveOutreachContextForContact(contact);
  const sender = String(profile?.fullName || "").trim();
  const sharedContext = String(contact?.shared_context || "").trim();
  const relationship = String(contact?.relationship_type || "beyond_network");
  if (relationship === "previous_company" && sharedContext) {
    return `Hi ${name}, having worked at ${sharedContext} as well, I wanted to connect because I'm interested in the ${role} role at ${company} and would appreciate any help getting in touch with the right contact. Thank you! ${sender.split(" ")[0] || "Venkatesh"}.`.slice(0, 280);
  }
  if (relationship === "school" && sharedContext) {
    return `Hi ${name}, having studied at ${sharedContext} as well, I wanted to connect because I'm interested in the ${role} role at ${company} and would appreciate any help getting in touch with the right contact. Thank you! ${sender.split(" ")[0] || "Venkatesh"}.`.slice(0, 280);
  }
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
  const { role, company } = deriveOutreachContextForContact(contact);
  const senderName = String(profile?.fullName || "Venkatesh Mudaliar").trim();
  const phone = String(profile?.phone || "(201) 275-6554").trim();
  const linkedin = String(profile?.linkedin || "linkedin.com/in/venkateshcmudaliar")
    .trim()
    .replace(/^https?:\/\/(?:www\.)?/i, "")
    .replace(/\/$/, "");
  const jobText = `${String(el.jobTitle?.value || "")} ${String(el.jobText?.value || "")}`.toLowerCase();
  let companyReason = `${company}'s emphasis on using data and technology to deliver measurable customer impact is especially compelling to me.`;
  let relevantSkill = "applied machine learning, analytics, and production data systems";
  if (/(agentic|llm|rag|generative ai|artificial intelligence)/i.test(jobText)) {
    companyReason = `${company}'s work applying AI and agentic systems to production business workflows is especially compelling to me.`;
    relevantSkill = "production LLM applications, RAG pipelines, and AI evaluation";
  } else if (/(etl|pipeline|data platform|spark|databricks)/i.test(jobText)) {
    companyReason = `${company}'s focus on reliable data platforms and scalable analytics infrastructure is especially compelling to me.`;
    relevantSkill = "building scalable data pipelines and data-quality systems";
  } else if (/(forecast|predictive|machine learning|data scientist|modeling)/i.test(jobText)) {
    companyReason = `${company}'s use of data science and predictive modeling to improve products and decisions is especially compelling to me.`;
    relevantSkill = "machine learning pipelines, model evaluation, and predictive analytics";
  }
  const subject = `Referral request: ${role} at ${company}`;
  const sharedContext = String(contact?.shared_context || "").trim();
  const relationship = String(contact?.relationship_type || "beyond_network");
  const sharedLine = relationship === "previous_company" && sharedContext
    ? `We both have experience at ${sharedContext}, which is why I especially wanted to reach out.`
    : relationship === "school" && sharedContext
      ? `As a fellow ${sharedContext} alum, I especially wanted to reach out.`
      : "";
  const body = [
    `Hi ${firstName},`,
    "",
    `I applied for the ${role} role at ${company} and came across your profile while researching the team.`,
    "",
    ...(sharedLine ? [sharedLine, ""] : []),
    "A bit about me - I completed my M.S. in Data Science at Stevens Institute (GPA 3.82) and have 4+ years of experience building ML pipelines, LLM evaluation frameworks, and predictive analytics systems at Accenture and LTIMindtree. I'm also an AWS Certified AI Practitioner.",
    "",
    `I'm genuinely interested in ${company} specifically because ${companyReason} I think my background in ${relevantSkill} maps well to what the team needs.`,
    "",
    "If you're open to it, I'd love a 15-minute call to learn more about the team's work and what you look for in candidates - and if it makes sense, I'd really appreciate a referral.",
    "",
    "Either way, thank you for your time.",
    "",
    "Best,",
    senderName,
    `${phone} | ${linkedin}`,
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
    String(el.jobTitle?.value || "").trim(),
    String(state.currentTitle || "").trim(),
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
    String(el.companyHint?.value || "").trim(),
    inferCompanyFromText(String(el.jobTitle?.value || "").trim()),
    String(state.currentCompany || "").trim(),
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
  el.jobText.value = cleanJobDescriptionForDisplay(el.jobText.value || "");
  const payload = {
    url: tab?.url || "",
    page_title: tab?.title || "",
    title_hint: cleanRoleForFilename(el.jobTitle.value || ""),
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
  const edited = cleanJobDescriptionForDisplay(String(el.jobText.value || "").trim());
  el.jobText.value = edited;
  if (edited.length < 50) {
    throw new Error("Edited text is too short. Paste at least 50 characters from the job description.");
  }
  const tab = await activeTab();
  const payload = {
    url: tab?.url || "",
    page_title: tab?.title || "",
    title_hint: cleanRoleForFilename(el.jobTitle.value || ""),
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

async function generateDocs() {
  if (!state.currentJobId) throw new Error("Analyze a job first.");
  if (state.analyzedFingerprint && state.analyzedFingerprint !== visibleJobFingerprint()) {
    throw new Error("The visible job details changed after the last analysis. Click Analyze from edited text before generating documents.");
  }
  const confirmed = window.confirm(
    "Generate final tailored documents now? This requires your explicit approval and uses your local profile facts only."
  );
  if (!confirmed) return null;

  return callApi("/generate_docs", "POST", {
    job_id: state.currentJobId,
    approve: true,
    boost_coverage: false,
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
      location: result.location || state.currentLocation || "",
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
      visibility: "private",
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
  el.downloadPdfPairBtn.onclick = async () => {
    try {
      const { profile } = await chrome.storage.local.get({ profile: {} });
      const title = sanitizeFilePart(resolveDownloadTitle());
      const company = sanitizeFilePart(resolveDownloadCompany());
      const name = sanitizeFilePart(profile?.fullName || "Candidate");
      await downloadGeneratedDoc(state.docs?.resume_pdf, `${title}_${company}_${name}_CV.pdf`);
      await downloadGeneratedDoc(state.docs?.cover_letter_pdf, `${title}_${company}_${name}_CoverLetter.pdf`);
      setStatus("Resume + cover letter PDF downloaded.");
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  };

  el.downloadDocxPairBtn.onclick = async () => {
    try {
      const { profile } = await chrome.storage.local.get({ profile: {} });
      const title = sanitizeFilePart(resolveDownloadTitle());
      const company = sanitizeFilePart(resolveDownloadCompany());
      const name = sanitizeFilePart(profile?.fullName || "Candidate");
      await downloadGeneratedDoc(state.docs?.resume_docx, `${title}_${company}_${name}_CV.docx`);
      await downloadGeneratedDoc(state.docs?.cover_letter_docx, `${title}_${company}_${name}_CoverLetter.docx`);
      setStatus("Resume + cover letter DOCX downloaded.");
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

el.openTrackerBtn?.addEventListener("click", openApplicationTracker);
el.saveOpenAiKeyInlineBtn?.addEventListener("click", saveInlineApiKeyState);
el.testOpenAiKeyInlineBtn?.addEventListener("click", testInlineApiKeyState);
el.removeOpenAiKeyInlineBtn?.addEventListener("click", removeInlineApiKeyState);

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
    setText(el.keywordCoverage, `${result.keyword_coverage_pct ?? 0}%`);
    setText(el.tailoredFitScore, result.tailored_fit_score != null ? `${result.tailored_fit_score}/100` : "Unavailable");
    setText(el.matchedKeywords, (result.matched_keywords || []).join(", ") || "None");
    setText(el.missingKeywords, (result.missing_keywords || []).join(", ") || "None");
    el.markAppliedBtn.disabled = false;
    setStatus(
      savedFolder
        ? `Documents ready below. Saved to ${savedFolder}. ${aiSourceLabel(result)}`
        : `Documents ready below. ${aiSourceLabel(result)}`
    );
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
    renderNetworkMatches(contacts);
    const lines = contactsToTextareaLines(contacts);
    el.referralContacts.value = lines;
    await chrome.storage.local.set({ referralContactsText: lines, referralContactsData: contacts });
    refreshReferralContactSelect();
    const alumniHits = contacts.filter((c) => c.relationship_type === "school").length;
    const expHits = contacts.filter((c) => c.relationship_type === "previous_company").length;
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
      state.referralContactsCache = mergeContactsPreservingContext(state.referralContactsCache, contacts);
      await chrome.storage.local.set({
        referralContactsText: raw,
        referralContactsData: state.referralContactsCache,
      });
    }
    refreshReferralContactSelect();
    const chosen = selectedContactOrFirst();
    if (!chosen) throw new Error("Add contacts first, then select one from dropdown.");
    let drafts = [];
    if (state.currentJobId) {
      const response = await callApi("/referral_drafts", "POST", { job_id: state.currentJobId, contacts: [chosen] });
      drafts = response.drafts || [];
    }
    if (!drafts.length) {
      const { profile } = await chrome.storage.local.get({ profile: {} });
      drafts = [{
        contact_name: chosen.name || "",
        contact_title: chosen.title || "",
        linkedin_url: chosen.linkedin_url || "",
        email: chosen.email || "",
        relationship_type: chosen.relationship_type || "beyond_network",
        shared_context: chosen.shared_context || "",
        linkedin_note: makeLinkedInNote(chosen, profile || {}),
        linkedin_followup: "",
        email_subject: "",
        email_body: "",
      }];
    }
    state.referralDrafts = drafts;
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
    if (contacts.length) state.referralContactsCache = mergeContactsPreservingContext(state.referralContactsCache, contacts);
    refreshReferralContactSelect();
    const chosen = selectedContactOrFirst();
    if (!chosen) throw new Error("Add contacts first, then select one from dropdown.");
    let apiDraft = null;
    if (state.currentJobId) {
      const response = await callApi("/referral_drafts", "POST", { job_id: state.currentJobId, contacts: [chosen] });
      apiDraft = (response.drafts || [])[0] || null;
    }
    const { profile } = await chrome.storage.local.get({ profile: {} });
    const localDraft = makeEmailDraft(chosen, profile || {});
    const subject = apiDraft?.email_subject || localDraft.subject;
    const body = apiDraft?.email_body || localDraft.body;
    const emailText = `Subject: ${subject}\n\n${body}`;
    if (el.referralOutput) {
      el.referralOutput.value = emailText;
    }
    const toEmail = String(chosen.email || "").trim();
    if (toEmail) {
      await chrome.tabs.create({
        url: buildGmailComposeUrl(toEmail, subject, body),
      });
    }
    state.referralDrafts = [
      {
        contact_name: chosen.name || "",
        contact_title: chosen.title || "",
        linkedin_url: chosen.linkedin_url || "",
        email: chosen.email || "",
        relationship_type: chosen.relationship_type || "beyond_network",
        shared_context: chosen.shared_context || "",
        linkedin_note: apiDraft?.linkedin_note || "",
        linkedin_followup: apiDraft?.linkedin_followup || "",
        email_subject: subject,
        email_body: body,
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
    referralContactsData: [],
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
  state.referralContactsCache = Array.isArray(cached.referralContactsData)
    ? cached.referralContactsData
    : [];
  if (!state.referralContactsCache.length && cached.referralContactsText) {
    state.referralContactsCache = parseReferralContacts(cached.referralContactsText);
  }
  renderNetworkMatches(state.referralContactsCache);
  refreshReferralContactSelect();
  await loadInlineApiKeyState();
  await refreshHistory();
  try {
    await extractFromPage();
  } catch {
    setStatus("Open a job page and click Analyze now.");
  }
})();
