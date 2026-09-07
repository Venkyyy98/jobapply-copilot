function textFromElement(el) {
  if (!el) return "";
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden") return "";
  return (el.innerText || "").trim();
}

function extractBySelectors() {
  const selectors = [
    "#job-description",
    "[data-test='job-description']",
    "[data-testid='job-description']",
    "main",
    "article",
    ".description",
    ".job-description",
    ".jobs-description"
  ];
  let best = "";
  for (const selector of selectors) {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
      const text = textFromElement(node);
      if (text.length > best.length) {
        best = text;
      }
    }
  }
  return best;
}

function fallbackVisibleText() {
  const main = document.querySelector("main") || document.body;
  const cloned = main.cloneNode(true);
  cloned.querySelectorAll("nav, footer, aside, script, style, noscript, form").forEach((n) => n.remove());
  return (cloned.innerText || "").trim();
}

function smartTrim(text, maxChars = 15000) {
  if (text.length <= maxChars) return text;
  const markers = ["requirements", "qualifications", "responsibilities", "preferred", "must have"];
  let bestIndex = maxChars;
  const lower = text.toLowerCase();
  for (const marker of markers) {
    const i = lower.lastIndexOf(marker, maxChars);
    if (i > 0) {
      bestIndex = Math.max(bestIndex, i + 2000);
    }
  }
  return text.slice(0, Math.min(bestIndex, text.length)).trim();
}

function htmlToVisibleText(value) {
  const container = document.createElement("div");
  container.innerHTML = String(value || "");
  return (container.innerText || container.textContent || "").trim();
}

function structuredJobPosting() {
  const scripts = Array.from(document.querySelectorAll("script[type='application/ld+json']"));
  for (const script of scripts) {
    try {
      const parsed = JSON.parse(script.textContent || "{}");
      const values = Array.isArray(parsed) ? parsed : [parsed];
      const queue = [...values];
      while (queue.length) {
        const item = queue.shift();
        if (!item || typeof item !== "object") continue;
        if (Array.isArray(item["@graph"])) queue.push(...item["@graph"]);
        const kind = String(item["@type"] || "").toLowerCase();
        if (kind !== "jobposting") continue;
        const organization = item.hiringOrganization || {};
        return {
          title: String(item.title || "").trim(),
          company: String(organization.name || "").trim(),
          description: htmlToVisibleText(item.description || ""),
        };
      }
    } catch {
      // Ignore malformed structured data and continue with visible page extraction.
    }
  }
  return { title: "", company: "", description: "" };
}

function cleanExtractedJobTitle(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^(?:job\s+)?application\s+for\s+/i, "")
    .replace(/\s+at\s+[A-Z][A-Za-z0-9&.,'()\- ]{1,80}$/i, "")
    .replace(/\s+job\s+in\s+.+$/i, "")
    .replace(/\s+(?:-|–|—)\s+[A-Z][A-Za-z .'-]+,\s*(?:[A-Z]{2}|[A-Z][A-Za-z .'-]+)$/i, "")
    .replace(/\s+in\s+[A-Z][A-Za-z .'-]+,\s*(?:[A-Z]{2}|[A-Z][A-Za-z .'-]+)$/i, "")
    .trim();
}

function companyFromJobTitle(value) {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  const match = raw.match(/\s+at\s+([A-Z][A-Za-z0-9&.,'()\- ]{1,80})$/i);
  return String(match?.[1] || "").trim();
}

function visibleJobTitle() {
  const selectors = [
    "main h1",
    "article h1",
    "[data-testid*='job-title']",
    "[data-test*='job-title']",
    ".job-title",
    "h1",
  ];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const title = cleanExtractedJobTitle(textFromElement(node));
      if (title && /\b(analyst|engineer|scientist|consultant|specialist|manager|intern|developer|co-?op)\b/i.test(title)) {
        return title;
      }
    }
  }
  return "";
}

function metadataCompany() {
  const selectors = [
    "meta[property='og:site_name']",
    "meta[name='application-name']",
    "meta[name='author']",
  ];
  for (const selector of selectors) {
    const value = String(document.querySelector(selector)?.getAttribute("content") || "")
      .replace(/\s+(careers?|jobs?)$/i, "")
      .trim();
    if (value && !/^(greenhouse|lever|ashby|workday)$/i.test(value)) return value;
  }
  return "";
}

function cleanExtractedJobText(text) {
  const noise = [
    /^skip to main content$/i,
    /^accept (all )?cookies$/i,
    /^cookie (preferences|settings|policy)$/i,
    /^privacy (choices|policy)$/i,
    /^we use cookies.*$/i,
    /^(req|job|requisition)\s*id\s*:?\s*$/i,
    /^(req|job|requisition)\s*id\s*:?\s*[a-z]{0,5}\d+$/i,
    /^[a-z]{1,5}\d{4,}\s+[a-z][a-z0-9 ,&/()#+.-]{0,80}$/i,
    /^share via (email|facebook|linkedin|twitter)$/i,
    /^apply now$/i,
    /^save job$/i,
    /^job details$/i,
    /^similar jobs$/i,
  ];
  return String(text || "")
    .replace(/\r/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !noise.some((pattern) => pattern.test(line)))
    .map((line) => line.replace(/^●\s*/, "- "))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function looksLikeJobDescription(text) {
  const value = String(text || "").toLowerCase();
  if (value.length < 120) return false;
  const signals = [
    "responsibilities",
    "qualifications",
    "requirements",
    "about the role",
    "what you'll do",
    "preferred qualifications",
    "minimum qualifications",
    "job description",
  ];
  return signals.some((signal) => value.includes(signal)) ||
    /\b(apply|position|role|hiring)\b/.test(value) && /\b(experience|skills|degree|python|sql|engineer|analyst|scientist)\b/.test(value);
}

function detectCaptcha() {
  const widgets = document.querySelectorAll(
    "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha, .h-captcha, [data-sitekey]"
  );
  for (const widget of widgets) {
    const style = window.getComputedStyle(widget);
    const rect = widget.getBoundingClientRect();
    const visible = style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    if (visible) return true;
  }
  return false;
}

function detectPlatform() {
  const host = (location.hostname || "").toLowerCase();
  if (host.includes("myworkdayjobs.com") || host.includes("workday")) return "workday";
  if (host.includes("greenhouse.io") || host.includes("boards.greenhouse")) return "greenhouse";
  if (host.includes("lever.co")) return "lever";
  return "generic";
}

function extractEmailsFromText(text) {
  const matches = String(text || "").match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [];
  const seen = new Set();
  const out = [];
  for (const m of matches) {
    const email = String(m).trim();
    const key = email.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(email);
  }
  return out;
}

function extractLinkedinContactsFromVisiblePage() {
  const host = (location.hostname || "").toLowerCase();
  const onLinkedIn = host.includes("linkedin.com");
  const links = Array.from(document.querySelectorAll("a[href*='/in/']")).filter((a) => isVisible(a));
  const seen = new Set();
  const contacts = [];
  for (const link of links) {
    const hrefRaw = String(link.getAttribute("href") || "");
    if (!hrefRaw) continue;
    const href = hrefRaw.startsWith("http") ? hrefRaw : new URL(hrefRaw, location.origin).toString();
    if (!/linkedin\.com\/in\//i.test(href)) continue;
    const key = href.split("?")[0].toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    const card = link.closest("li, article, div[data-view-name], div.entity-result, .reusable-search__result-container, .org-people-profile-card");
    const context = normalizeSpace((card?.innerText || link.innerText || "").slice(0, 600));
    if (!context) continue;
    const lines = context
      .split("\n")
      .map((x) => normalizeSpace(x))
      .filter(Boolean);
    const name = normalizeSpace(link.innerText || lines[0] || "").replace(/^\d+\.\s*/, "");
    const title = lines.find((ln) => ln !== name && ln.length > 6) || "";
    const emails = extractEmailsFromText(context);
    contacts.push({
      name: name || "",
      title: title || "",
      linkedin_url: href,
      email: emails[0] || "",
      context,
    });
    if (contacts.length >= 40) break;
  }
  return {
    onLinkedIn,
    contacts,
    warnings: contacts.length ? [] : ["No visible LinkedIn profile cards detected on this page. Open a LinkedIn company People/search page and retry."],
  };
}

function labelTextForField(field) {
  const id = field.getAttribute("id");
  if (id) {
    const label = document.querySelector(`label[for='${CSS.escape(id)}']`);
    if (label) return label.innerText.trim().toLowerCase();
  }
  const labelledBy = field.getAttribute("aria-labelledby");
  if (labelledBy) {
    const ids = labelledBy.split(/\s+/).filter(Boolean);
    const text = ids
      .map((x) => document.getElementById(x))
      .filter(Boolean)
      .map((el) => (el.innerText || "").trim())
      .join(" ")
      .trim();
    if (text) return text.toLowerCase();
  }
  const wrapperLabel = field.closest("label");
  if (wrapperLabel) return wrapperLabel.innerText.trim().toLowerCase();
  const aria = (field.getAttribute("aria-label") || "").toLowerCase();
  const placeholder = (field.getAttribute("placeholder") || "").toLowerCase();
  const autoId = (field.getAttribute("data-automation-id") || "").toLowerCase();
  const name = (field.getAttribute("name") || "").toLowerCase();
  return [aria, placeholder, autoId, name].filter(Boolean).join(" ").trim();
}

function localQuestionForField(field) {
  let node = field;
  for (let i = 0; i < 7 && node; i += 1) {
    const parent = node.parentElement;
    if (!parent) break;
    const prev = parent.previousElementSibling;
    if (prev) {
      const t = normalizeSpace(prev.innerText || "").toLowerCase();
      if (t && (t.includes("?") || /eligible to work|sponsorship|work visa|authorized|salary/i.test(t))) {
        return t.slice(0, 300);
      }
    }
    node = parent;
  }
  return "";
}

function firstExp(profile) {
  return (Array.isArray(profile.workExperiences) ? profile.workExperiences : [])[0] || {};
}

function secondExp(profile) {
  return (Array.isArray(profile.workExperiences) ? profile.workExperiences : [])[1] || {};
}

function firstEdu(profile) {
  return (Array.isArray(profile.education) ? profile.education : [])[0] || {};
}

function resolveAddressForContext(profile) {
  try {
    const combined = `${String(location.href || "").toLowerCase()} ${String(document.body?.innerText || "").slice(0, 3000).toLowerCase()}`;
    const caPattern = /\b(california|san francisco|sf bay|bay area|los angeles|san jose|palo alto|mountain view|sunnyvale|santa clara|fremont|oakland|berkeley|sacramento|san diego|irvine|antioch\b|94\d{3})\b/;
    if (caPattern.test(combined) && (profile.addressLine1Ca || profile.cityCa)) {
      return { line1: profile.addressLine1Ca || "", city: profile.cityCa || "", state: profile.stateCa || "CA", zip: profile.zipCa || "" };
    }
  } catch { /* ignore */ }
  return { line1: profile.addressLine1NjNy || "", city: profile.cityNjNy || "", state: profile.stateNjNy || "", zip: profile.zipNjNy || "" };
}

function mapProfileToField(label, profile) {
  const normalized = label.toLowerCase();
  const fullName = String(profile.fullName || "").trim();
  const parts = fullName.split(/\s+/).filter(Boolean);
  const derivedFirst = profile.firstName || parts[0] || "";
  const derivedLast = profile.lastName || (parts.length > 1 ? parts[parts.length - 1] : "");
  const addr = resolveAddressForContext(profile);
  const exp0 = firstExp(profile);
  const exp1 = secondExp(profile);
  const edu0 = firstEdu(profile);

  // EEO & Demographics — checked first to prevent collision with generic name/location matchers
  if (/\bpreferred name\b|\bgoes by\b|\bnickname\b|\bpreferred first\b|\bdisplay name\b/.test(normalized)) return profile.preferredName || "";
  if (/\bgender\b|\bsex\b/.test(normalized) && !/biological|assigned/.test(normalized)) return profile.gender || "";
  if (/\bpronoun\b/.test(normalized)) return profile.pronouns || "";
  if (/\bhispanic\b|\blatino\b|\blatinx\b/.test(normalized)) return profile.hispanicOrLatino || "";
  if (/\brace\b|\bethnicity\b|\bracial\b/.test(normalized)) return profile.raceEthnicity || "";
  if (/\bveteran\b|\bprotected veteran\b|\bmilitary service\b/.test(normalized)) return profile.veteranStatus || "";
  if (/\bdisabilit\b|\bdisabled\b/.test(normalized)) return profile.disabilityStatus || "";

  // Education fields — match when in an education context or specific edu labels are present
  const inEduCtx = /\b(education|degree|academic|qualification|graduate|university|college|school|study|institution)\b/.test(normalized);
  if (inEduCtx || /\bfield of study\b|\bmajor\b|\bgpa\b|\bgrad year\b|\bgraduation year\b/.test(normalized)) {
    if (/\bdegree\b|\bhighest education\b|\blevel of education\b/.test(normalized)) return edu0.degree || profile.educationDegree || "";
    if (/\bfield of study\b|\bmajor\b|\bprogram\b|\bconcentration\b|\barea of study\b/.test(normalized) && !/field of work/.test(normalized)) return edu0.field || profile.educationField || "";
    if (/\bschool\b|\buniversity\b|\bcollege\b|\binstitution\b/.test(normalized) && inEduCtx) return edu0.school || profile.educationSchool || "";
    if (/\bgpa\b|\bgrade point\b/.test(normalized)) return edu0.gpa || profile.educationGpa || "";
    if (/\bgrad(uation)? year\b|\bend year\b|\bclass of\b/.test(normalized)) return edu0.endYear || edu0.gradYear || profile.educationEndYear || "";
    if (/\bstart year\b/.test(normalized) && inEduCtx) return edu0.startYear || profile.educationStartYear || "";
  }

  // Work experience fields — match when explicit experience context is present
  const inExpCtx = /\b(work experience|employment|current employer|most recent employer|previous employer|job history|work history|professional experience)\b/.test(normalized);
  if (inExpCtx) {
    const isPrev = /\bprevious\b|\bformer\b|\bprior\b|\bpast\b/.test(normalized);
    const expEntry = isPrev ? exp1 : exp0;
    if (/\bcompany\b|\bemployer\b|\borganization\b/.test(normalized)) return expEntry.company || "";
    if (/\btitle\b|\bposition\b|\brole\b/.test(normalized) && !/role family/.test(normalized)) return expEntry.title || "";
    if (/\bstart\b.*\bdate\b|\bdate.*\bstart\b/.test(normalized)) return expEntry.startDate || "";
    if (/\bend\b.*\bdate\b|\bdate.*\bend\b/.test(normalized)) return expEntry.endDate || "Present";
    if (/\bdescription\b|\bresponsibilit\b|\bduties\b/.test(normalized)) return expEntry.description || "";
  }

  // Address — specific patterns before generic location
  if (/\bstreet address\b|\baddress line 1\b|\baddress line1\b/.test(normalized) && !/email/.test(normalized)) return addr.line1;
  if (/\bzip\b|\bpostal code\b|\bzipcode\b/.test(normalized)) return addr.zip;

  // Standard profile fields
  const checks = [
    { keys: ["first name", "given name"], value: derivedFirst },
    { keys: ["last name", "surname", "family name"], value: derivedLast },
    { keys: ["full name", "legal name", "name"], value: fullName },
    { keys: ["email"], value: profile.email || "" },
    { keys: ["phone", "mobile", "telephone"], value: profile.phone || "" },
    { keys: ["linkedin"], value: profile.linkedin || "" },
    { keys: ["github"], value: profile.github || "" },
    { keys: ["portfolio", "website"], value: profile.portfolio || "" },
    { keys: ["state", "province", "region"], value: derivedProfile(profile).state || "" },
    { keys: ["city"], value: addr.city || profile.location || "" },
    { keys: ["work authorization"], value: profile.workAuthorization || "" },
    { keys: ["sponsorship"], value: profile.sponsorship || "" },
    { keys: ["location"], value: profile.location || "" },
    { keys: ["salary range", "desired salary", "compensation"], value: profile.desiredSalaryRange || "" },
  ];

  for (const item of checks) {
    if (item.keys.some((k) => normalized.includes(k))) {
      return item.value;
    }
  }
  return "";
}

function mapProfileToNameOrId(field, profile) {
  const key = `${field.getAttribute("name") || ""} ${field.getAttribute("id") || ""}`.toLowerCase();
  const fullName = String(profile.fullName || "").trim();
  const parts = fullName.split(/\s+/).filter(Boolean);
  const derivedFirst = profile.firstName || parts[0] || "";
  const derivedLast = profile.lastName || (parts.length > 1 ? parts[parts.length - 1] : "");

  const rules = [
    { re: /\b(first|given).*name\b/, value: derivedFirst },
    { re: /\b(last|family|sur).*name\b/, value: derivedLast },
    { re: /\b(full)?.*name\b/, value: fullName },
    { re: /\bemail\b/, value: profile.email || "" },
    { re: /\b(phone|mobile|tel)\b/, value: profile.phone || "" },
    { re: /\blinkedin\b/, value: profile.linkedin || "" },
    { re: /\bgithub\b/, value: profile.github || "" },
    { re: /\b(portfolio|website|url)\b/, value: profile.portfolio || "" },
    { re: /\b(location|city)\b/, value: profile.location || "" },
    { re: /\b(state|province|region)\b/, value: derivedProfile(profile).state || "" },
    { re: /\b(auth|authorization|work_permit)\b/, value: profile.workAuthorization || "" },
    { re: /\b(sponsor|sponsorship)\b/, value: profile.sponsorship || "" },
    { re: /\b(salary|compensation|pay|ctc)\b/, value: profile.desiredSalaryRange || "" },
  ];
  for (const rule of rules) {
    if (rule.re.test(key) && rule.value) return String(rule.value);
  }
  return "";
}

function mapProfileByPlatform(field, profile, platform) {
  const key = `${field.getAttribute("name") || ""} ${field.getAttribute("id") || ""}`.toLowerCase();
  const fullName = String(profile.fullName || "").trim();
  const parts = fullName.split(/\s+/).filter(Boolean);
  const firstName = profile.firstName || parts[0] || "";
  const lastName = profile.lastName || (parts.length > 1 ? parts[parts.length - 1] : "");

  if (platform === "greenhouse") {
    const rules = [
      { re: /\bfirst_name\b/, value: firstName },
      { re: /\blast_name\b/, value: lastName },
      { re: /\bemail\b/, value: profile.email || "" },
      { re: /\bphone\b/, value: profile.phone || "" },
      { re: /\blinkedin\b/, value: profile.linkedin || "" },
      { re: /\b(website|portfolio)\b/, value: profile.portfolio || "" },
      { re: /\bgithub\b/, value: profile.github || "" },
      { re: /\bauthori(z|s)ation\b/, value: profile.workAuthorization || "" },
      { re: /\bsponsor(ship)?\b/, value: profile.sponsorship || "" },
    ];
    for (const rule of rules) {
      if (rule.re.test(key) && rule.value) return String(rule.value);
    }
  }

  if (platform === "workday") {
    const rules = [
      { re: /\bgiven(name)?\b/, value: firstName },
      { re: /\bfamily(name)?\b/, value: lastName },
      { re: /\blegalname\b/, value: fullName },
      { re: /\bemail\b/, value: profile.email || "" },
      { re: /\bphone(number)?\b/, value: profile.phone || "" },
      { re: /\blinkedin(profile)?\b/, value: profile.linkedin || "" },
      { re: /\b(website|portfolio)\b/, value: profile.portfolio || "" },
      { re: /\bgithub\b/, value: profile.github || "" },
      { re: /\b(city|location)\b/, value: profile.location || "" },
      { re: /\b(state|province|region)\b/, value: derivedProfile(profile).state || "" },
      { re: /\bworkauthori(z|s)ation\b/, value: profile.workAuthorization || "" },
      { re: /\bsponsor(ship)?\b/, value: profile.sponsorship || "" },
    ];
    for (const rule of rules) {
      if (rule.re.test(key) && rule.value) return String(rule.value);
    }
  }

  return "";
}

function derivedProfile(profile) {
  const fullName = String(profile.fullName || "").trim();
  const parts = fullName.split(/\s+/).filter(Boolean);
  const location = String(profile.location || "").trim();
  const explicitState = String(profile.state || "").trim();
  const derivedState = explicitState || inferUsStateFromLocation(location);
  return {
    ...profile,
    firstName: profile.firstName || parts[0] || "",
    lastName: profile.lastName || (parts.length > 1 ? parts[parts.length - 1] : ""),
    fullName,
    state: derivedState,
  };
}

function inferUsStateFromLocation(location) {
  const raw = String(location || "").toLowerCase();
  if (!raw) return "";
  const states = [
    ["alabama", "AL"], ["alaska", "AK"], ["arizona", "AZ"], ["arkansas", "AR"], ["california", "CA"],
    ["colorado", "CO"], ["connecticut", "CT"], ["delaware", "DE"], ["florida", "FL"], ["georgia", "GA"],
    ["hawaii", "HI"], ["idaho", "ID"], ["illinois", "IL"], ["indiana", "IN"], ["iowa", "IA"],
    ["kansas", "KS"], ["kentucky", "KY"], ["louisiana", "LA"], ["maine", "ME"], ["maryland", "MD"],
    ["massachusetts", "MA"], ["michigan", "MI"], ["minnesota", "MN"], ["mississippi", "MS"], ["missouri", "MO"],
    ["montana", "MT"], ["nebraska", "NE"], ["nevada", "NV"], ["new hampshire", "NH"], ["new jersey", "NJ"],
    ["new mexico", "NM"], ["new york", "NY"], ["north carolina", "NC"], ["north dakota", "ND"], ["ohio", "OH"],
    ["oklahoma", "OK"], ["oregon", "OR"], ["pennsylvania", "PA"], ["rhode island", "RI"], ["south carolina", "SC"],
    ["south dakota", "SD"], ["tennessee", "TN"], ["texas", "TX"], ["utah", "UT"], ["vermont", "VT"],
    ["virginia", "VA"], ["washington", "WA"], ["west virginia", "WV"], ["wisconsin", "WI"], ["wyoming", "WY"],
    ["district of columbia", "DC"], ["washington dc", "DC"]
  ];
  for (const [name, abbr] of states) {
    if (raw.includes(name)) return name.replace(/\b\w/g, (c) => c.toUpperCase());
    if (new RegExp(`(^|[^a-z])${abbr.toLowerCase()}([^a-z]|$)`).test(raw)) return name.replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return "";
}

function aiFieldValueByKey(profile, key) {
  const p = derivedProfile(profile || {});
  const exp0 = firstExp(profile);
  const exp1 = secondExp(profile);
  const edu0 = firstEdu(profile);
  const addr = resolveAddressForContext(profile);
  const map = {
    first_name: p.firstName || "",
    last_name: p.lastName || "",
    full_name: p.fullName || "",
    preferred_name: profile.preferredName || "",
    email: p.email || "",
    phone: p.phone || "",
    linkedin: p.linkedin || "",
    github: p.github || "",
    portfolio: p.portfolio || "",
    location: p.location || "",
    state: p.state || "",
    work_authorization: p.workAuthorization || "",
    sponsorship: p.sponsorship || "",
    desired_salary_range: p.desiredSalaryRange || "",
    gender: profile.gender || "",
    pronouns: profile.pronouns || "",
    hispanic_or_latino: profile.hispanicOrLatino || "",
    race_ethnicity: profile.raceEthnicity || "",
    veteran_status: profile.veteranStatus || "",
    disability_status: profile.disabilityStatus || "",
    current_company: exp0.company || "",
    current_title: exp0.title || "",
    current_start_date: exp0.startDate || "",
    current_end_date: exp0.endDate || "",
    current_description: exp0.description || "",
    previous_company: exp1.company || "",
    previous_title: exp1.title || "",
    previous_description: exp1.description || "",
    education_degree: edu0.degree || profile.educationDegree || "",
    education_field: edu0.field || profile.educationField || "",
    education_school: edu0.school || profile.educationSchool || "",
    education_gpa: edu0.gpa || profile.educationGpa || "",
    education_grad_year: edu0.endYear || edu0.gradYear || profile.educationEndYear || "",
    street_address: addr.line1,
    address_city: addr.city,
    zip_code: addr.zip,
  };
  return map[key] || "";
}

function aiScoreField(field, profile) {
  const label = labelTextForField(field);
  const context = `${label} ${field.getAttribute("name") || ""} ${field.getAttribute("id") || ""} ${(field.getAttribute("placeholder") || "")}`.toLowerCase();
  const aliases = {
    first_name: ["first name", "given name", "firstname", "given"],
    last_name: ["last name", "surname", "family name", "lastname", "family"],
    full_name: ["full name", "legal name", "name"],
    preferred_name: ["preferred name", "preferred first name", "display name", "goes by", "nickname"],
    email: ["email", "e-mail"],
    phone: ["phone", "mobile", "telephone", "tel"],
    linkedin: ["linkedin"],
    github: ["github"],
    portfolio: ["portfolio", "website", "personal site", "url"],
    location: ["location", "address"],
    state: ["state", "province", "region"],
    work_authorization: ["work authorization", "authorized", "work permit", "eligible to work"],
    sponsorship: ["sponsorship", "sponsor", "visa support", "require visa"],
    gender: ["gender", "sex"],
    pronouns: ["pronouns", "preferred pronouns"],
    hispanic_or_latino: ["hispanic", "latino", "latinx", "hispanic or latino"],
    race_ethnicity: ["race", "ethnicity", "racial background"],
    veteran_status: ["veteran", "military service", "protected veteran", "veteran status"],
    disability_status: ["disability", "disabled", "accommodation"],
    current_company: ["current employer", "current company", "most recent employer", "employer name", "company name"],
    current_title: ["current job title", "current position", "most recent position", "job title", "position title"],
    current_start_date: ["current start date", "start of employment", "employment start"],
    current_end_date: ["current end date", "end of employment"],
    current_description: ["responsibilities", "duties", "role description", "job description"],
    previous_company: ["previous employer", "former employer", "prior employer"],
    previous_title: ["previous title", "former title", "prior position"],
    education_degree: ["degree", "degree type", "highest degree", "level of education"],
    education_field: ["field of study", "major", "program of study", "area of study", "concentration"],
    education_school: ["school name", "university", "college", "institution"],
    education_gpa: ["gpa", "grade point average", "cumulative gpa"],
    education_grad_year: ["graduation year", "year of graduation", "grad year", "end year"],
    street_address: ["street address", "address line 1", "address line1"],
    address_city: ["city name"],
    zip_code: ["zip code", "postal code", "zipcode"],
  };

  let bestKey = "";
  let bestScore = 0;
  for (const [key, terms] of Object.entries(aliases)) {
    let score = 0;
    for (const term of terms) {
      if (context.includes(term)) {
        score += term.includes(" ") ? 0.45 : 0.25;
      }
    }
    if (/\bfirst\b/.test(context) && key === "first_name") score += 0.25;
    if (/\blast\b|\bsur\b|\bfamily\b/.test(context) && key === "last_name") score += 0.25;
    if (score > bestScore) {
      bestScore = score;
      bestKey = key;
    }
  }
  const value = aiFieldValueByKey(profile, bestKey);
  return { key: bestKey, score: Math.min(1, bestScore), value };
}

function fillField(field, value) {
  field.focus();
  const setter = Object.getOwnPropertyDescriptor(field.__proto__, "value")?.set;
  if (setter) {
    setter.call(field, value);
  } else {
    field.value = value;
  }
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  field.style.outline = "2px solid #0ea5e9";
}

function normalizeChoiceText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function yesNoAliases(want) {
  const low = normalizeChoiceText(want);
  if (!low) return [];
  if (["yes", "y", "true"].includes(low)) return ["yes", "y", "true"];
  if (["no", "n", "false"].includes(low)) return ["no", "n", "false"];
  return [low];
}

function optionTextBag(opt) {
  return normalizeChoiceText(
    `${opt?.textContent || ""} ${opt?.value || ""} ${opt?.label || ""} ${opt?.getAttribute?.("aria-label") || ""}`
  );
}

function optionScore(optionBag, desiredText) {
  const desired = normalizeChoiceText(desiredText);
  if (!desired || !optionBag) return 0;
  const aliases = yesNoAliases(desired);
  for (const alias of aliases) {
    if (optionBag === alias) return 1;
  }
  for (const alias of aliases) {
    if (new RegExp(`(^|\\s)${alias}(\\s|$)`).test(optionBag)) return 0.95;
  }
  if (optionBag.includes(desired)) return 0.82;
  const desiredTokens = desired.split(" ").filter((t) => t.length > 1);
  const optionTokens = optionBag.split(" ").filter((t) => t.length > 1);
  if (!desiredTokens.length || !optionTokens.length) return 0;
  let overlap = 0;
  for (const token of desiredTokens) {
    if (optionTokens.includes(token)) overlap += 1;
  }
  return overlap / Math.max(desiredTokens.length, optionTokens.length);
}

function fillSelectField(field, desired) {
  const want = normalizeChoiceText(desired);
  if (!want) return false;
  const options = Array.from(field.options || []);
  let matched = null;
  let bestScore = 0;
  for (const opt of options) {
    const bag = optionTextBag(opt);
    if (!bag) continue;
    if (/^select one$|^choose one$|^please select$/.test(bag)) continue;
    const score = optionScore(bag, want);
    if (score > bestScore) {
      bestScore = score;
      matched = opt;
    }
  }
  if (!matched && stateValues({ state: desired }).length > 0) {
    const stateCandidates = stateValues({ state: desired }).map((x) => normalizeChoiceText(x));
    matched = options.find((opt) => {
      const bag = optionTextBag(opt);
      return stateCandidates.some((s) => s && (bag === s || bag.includes(s)));
    });
  }
  if (bestScore < 0.5 && !matched) return false;
  if (!matched) return false;
  field.value = matched.value;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  field.style.outline = "2px solid #0ea5e9";
  return true;
}

function hasMeaningfulExistingValue(field) {
  const v = normalizeSpace(field?.value || "").toLowerCase();
  if (!v) return false;
  if (/^select one$|^choose one$|^please select$|^no items\.?$/.test(v)) return false;
  return true;
}

function chooseBooleanByLabel(label, profile) {
  const normalized = label.toLowerCase();
  const custom = customAnswerForQuestion(normalized, profile || {});
  if (custom) {
    const low = String(custom).toLowerCase();
    if (low.includes("yes")) return "yes";
    if (low.includes("no")) return "no";
  }
  if (normalized.includes("sponsorship")) {
    const raw = String(profile.sponsorship || "").toLowerCase();
    if (raw.includes("no")) return "no";
    if (raw.includes("yes")) return "yes";
  }
  if (/\b18\b/.test(normalized) || normalized.includes("18 years or older") || normalized.includes("age")) {
    const raw = String(profile.age18Plus || "yes").toLowerCase();
    if (raw.includes("no")) return "no";
    return "yes";
  }
  if (normalized.includes("eligible to work for any employer") || normalized.includes("eligible to work")) {
    const raw = String(profile.workAuthorization || "").toLowerCase();
    if (raw.includes("yes") || raw.includes("authorized") || raw.includes("eligible")) return "yes";
    if (raw.includes("no") || raw.includes("not")) return "no";
  }
  if (normalized.includes("authorized") || normalized.includes("authorization") || normalized.includes("work permit")) {
    const raw = String(profile.workAuthorization || "").toLowerCase();
    if (raw.includes("yes") || raw.includes("authorized")) return "yes";
    if (raw.includes("no") || raw.includes("not")) return "no";
  }
  if (normalized.includes("salary within your range") || normalized.includes("salary range")) {
    const raw = String(profile.salaryInRange || "yes").toLowerCase();
    if (raw.includes("yes")) return "yes";
    if (raw.includes("no")) return "no";
  }
  if (normalized.includes("primary residence") || normalized.includes("based in the united states")) {
    const loc = String(profile.location || "").toLowerCase();
    if (/\bunited states\b|\busa\b|\bu\.s\.\b/.test(loc)) return "yes";
    return "no";
  }
  if (normalized.includes("agreement with a current or former employer") ||
      normalized.includes("prohibits or impacts your ability to work")) {
    const raw = String(profile.employmentRestriction || "no").toLowerCase();
    if (raw.includes("yes")) return "yes";
    return "no";
  }
  if (/\b(veteran|protected veteran|military service|veteran status)\b/.test(normalized)) {
    const raw = String(profile.veteranStatus || "no").toLowerCase();
    return (raw.includes("yes") || (raw.includes("veteran") && !raw.includes("not") && !raw.includes("no"))) ? "yes" : "no";
  }
  if (/\bdisabilit/.test(normalized)) {
    const raw = String(profile.disabilityStatus || "no").toLowerCase();
    return raw.includes("yes") ? "yes" : "no";
  }
  if (/\b(hispanic|latino|latinx)\b/.test(normalized)) {
    const raw = String(profile.hispanicOrLatino || "no").toLowerCase();
    return raw.includes("yes") ? "yes" : "no";
  }
  return "";
}

function stateValues(profile) {
  const p = derivedProfile(profile || {});
  const state = String(p.state || "").trim();
  if (!state) return [];
  const lower = state.toLowerCase();
  const abbrMap = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
  };
  const values = [state];
  if (abbrMap[lower]) {
    values.push(abbrMap[lower]);
  } else {
    for (const [name, abbr] of Object.entries(abbrMap)) {
      if (lower === abbr.toLowerCase()) {
        values.push(name.replace(/\b\w/g, (c) => c.toUpperCase()));
        values.push(abbr);
        break;
      }
    }
  }
  if (lower === "washington dc") values.push("DC");
  return values;
}

function customAnswerForQuestion(context, profile) {
  const qa = Array.isArray(profile.customQa) ? profile.customQa : [];
  const lowContext = String(context || "").toLowerCase();
  for (const item of qa) {
    const q = String(item?.question || "").trim().toLowerCase();
    const a = String(item?.answer || "").trim();
    if (!q || !a) continue;
    if (lowContext.includes(q)) return a;
  }
  const bank = questionBankAnswerForQuestion(context, profile || {});
  if (bank) return bank;
  return "";
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

function questionTokens(text) {
  return canonicalQuestion(text)
    .split(" ")
    .map((x) => x.trim())
    .filter((x) => x.length >= 3);
}

function tokenOverlapScore(aText, bText) {
  const a = questionTokens(aText);
  const b = questionTokens(bText);
  if (!a.length || !b.length) return 0;
  const bSet = new Set(b);
  let hits = 0;
  for (const token of a) {
    if (bSet.has(token)) hits += 1;
  }
  return hits / Math.max(a.length, b.length);
}

function questionBankAnswerForQuestion(context, profile) {
  const items = Array.isArray(profile.questionBank) ? profile.questionBank : [];
  if (!items.length) return "";
  const lowContext = String(context || "").trim();
  if (!lowContext) return "";

  let best = "";
  let bestScore = 0;
  for (const item of items) {
    const q = String(item?.question || "").trim();
    const a = String(item?.answer || "").trim();
    if (!q || !a) continue;
    const qCanon = canonicalQuestion(q);
    const cCanon = canonicalQuestion(lowContext);
    if (!qCanon || !cCanon) continue;
    if (cCanon.includes(qCanon) || qCanon.includes(cCanon)) {
      return a;
    }
    const score = tokenOverlapScore(qCanon, cCanon);
    if (score > bestScore) {
      bestScore = score;
      best = a;
    }
  }
  if (bestScore >= 0.55) return best;
  return "";
}

function mappedDropdownValue(context, profile) {
  const mappings = Array.isArray(profile.dropdownMap) ? profile.dropdownMap : [];
  const lowContext = String(context || "").toLowerCase();
  const normContext = normalizeLookupText(lowContext);
  for (const item of mappings) {
    const key = String(item?.key || "").trim().toLowerCase();
    const value = String(item?.value || "").trim();
    if (!key || !value) continue;
    const normKey = normalizeLookupText(key);
    if (!normKey) continue;
    if (lowContext.includes(key) || normContext.includes(normKey)) return value;

    // Fuzzy fallback: if most key tokens appear in context, treat as a match.
    const keyTokens = normKey.split(" ").filter((t) => t.length > 2);
    if (!keyTokens.length) continue;
    let hits = 0;
    for (const t of keyTokens) {
      if (normContext.includes(t)) hits += 1;
    }
    if (hits / keyTokens.length >= 0.65) return value;
  }
  return "";
}

function normalizeLookupText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function skillValues(profile) {
  const raw = String(profile?.skillsList || "").trim();
  if (!raw) return [];
  return raw
    .split(/[\n,]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .filter((x, i, arr) => arr.findIndex((y) => y.toLowerCase() === x.toLowerCase()) === i)
    .slice(0, 25);
}

function isVisible(el) {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
}

function normalizeSpace(text) {
  return String(text || "").trim().replace(/\s+/g, " ");
}

function chooseAnswerFromQuestionText(questionText, profile) {
  const custom = customAnswerForQuestion(questionText, profile || {});
  if (custom) return String(custom).trim();
  const bank = questionBankAnswerForQuestion(questionText, profile || {});
  if (bank) return String(bank).trim();
  const yn = chooseBooleanByLabel(questionText, profile || {});
  if (yn === "yes") return "Yes";
  if (yn === "no") return "No";
  return "";
}

function clickElementSafely(el) {
  if (!el || !isVisible(el)) return false;
  let target = el;
  let cursor = el;
  for (let i = 0; i < 6 && cursor; i += 1) {
    const role = (cursor.getAttribute && cursor.getAttribute("role")) || "";
    const cls = (cursor.className || "").toString().toLowerCase();
    const style = window.getComputedStyle(cursor);
    if (
      /^(button|radio|option|checkbox|switch)$/.test(role) ||
      cursor.tagName === "BUTTON" ||
      cursor.tagName === "LABEL" ||
      cursor.hasAttribute?.("tabindex") ||
      typeof cursor.onclick === "function" ||
      style.cursor === "pointer" ||
      /radio|option|checkbox|toggle|select/.test(cls)
    ) {
      target = cursor;
      break;
    }
    cursor = cursor.parentElement;
  }
  const activate = (node) => {
    if (!node || !isVisible(node)) return false;
    node.scrollIntoView({ block: "center", behavior: "smooth" });
    const events = ["pointerdown", "mousedown", "pointerup", "mouseup", "click"];
    for (const type of events) {
      node.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
    }
    if (typeof node.click === "function") node.click();
    node.style.outline = "2px solid #0ea5e9";
    return true;
  };

  if (activate(target)) return true;

  if (target.tagName === "LABEL" && target.control) {
    if (activate(target.control)) return true;
  }

  const fallbacks = [
    target.previousElementSibling,
    target.nextElementSibling,
    target.parentElement,
    target.parentElement?.previousElementSibling,
    target.parentElement?.nextElementSibling,
  ].filter(Boolean);
  for (const node of fallbacks) {
    if (activate(node)) return true;
  }
  return false;
}

function setRadioChecked(input) {
  if (!input || input.type !== "radio") return false;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
  if (setter) setter.call(input, true);
  else input.checked = true;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  input.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
  input.style.outline = "2px solid #0ea5e9";
  return true;
}

function setRadioChoiceInBlock(block, desired) {
  if (!block || !desired) return false;
  const wantYes = String(desired).toLowerCase() === "yes";
  const radios = Array.from(block.querySelectorAll("input[type='radio']"));
  if (!radios.length) return false;

  const labelsById = new Map();
  Array.from(block.querySelectorAll("label[for]")).forEach((label) => {
    const id = label.getAttribute("for");
    if (!id) return;
    labelsById.set(id, normalizeSpace(label.innerText).toLowerCase());
  });

  const scoreRadio = (radio) => {
    const context = normalizeSpace(
      `${radio.value || ""} ${radio.id || ""} ${radio.name || ""} ${radio.getAttribute("aria-label") || ""} ${radio.getAttribute("data-testid") || ""} ${
        labelsById.get(radio.id) || ""
      }`
    ).toLowerCase();
    let score = 0;
    if (wantYes && /\byes|true|authorized|eligible\b/.test(context)) score += 2;
    if (!wantYes && /\bno|false|not\b/.test(context)) score += 2;
    if (wantYes && /\bno|false|not\b/.test(context)) score -= 1;
    if (!wantYes && /\byes|true|authorized|eligible\b/.test(context)) score -= 1;
    if (radio.checked) score += 0.2;
    return score;
  };

  const scored = radios.map((r) => ({ radio: r, score: scoreRadio(r) })).sort((a, b) => b.score - a.score);
  if (scored.length && scored[0].score > 0.5) {
    return setRadioChecked(scored[0].radio);
  }

  if (radios.length === 2) {
    return setRadioChecked(wantYes ? radios[0] : radios[1]);
  }
  return false;
}

function binaryOptionElements(root = document) {
  const nodes = Array.from(root.querySelectorAll("label, button, [role='radio'], [role='option'], div, span, p"));
  return nodes.filter((el) => {
    if (!isVisible(el)) return false;
    const txt = normalizeSpace(el.innerText).toLowerCase();
    if (!txt || txt.length > 18) return false;
    if (txt === "yes" || txt === "no") return true;
    if (/^(o|\(|\[)?\s*yes\s*$/.test(txt)) return true;
    if (/^(o|\(|\[)?\s*no\s*$/.test(txt)) return true;
    return /\byes$/.test(txt) || /\bno$/.test(txt);
  });
}

function answerQuestionBlocks(profile, recorder = null) {
  const blocks = Array.from(
    document.querySelectorAll("fieldset, [role='group'], [role='radiogroup'], .application-question, .question, .form-group, section, div")
  );
  let changed = 0;
  const clickedKeys = new Set();

  for (const block of blocks) {
    if (!isVisible(block)) continue;
    const text = normalizeSpace(block.innerText);
    if (!text) continue;
    if (/\b(sms|whatsapp|text alert|newsletter|marketing|promotional|recruitment campaign|talent community)\b/i.test(text.slice(0, 200))) continue;
    if (!/authorized to work|sponsorship|primary residence|salary within your range|require sponsorship/i.test(text)) {
      const custom = customAnswerForQuestion(text, profile || {});
      if (!custom) continue;
    }
    const desired = chooseAnswerFromQuestionText(text, profile || {});
    if (!desired) continue;

    const key = `${text.slice(0, 180).toLowerCase()}|${desired.toLowerCase()}`;
    if (clickedKeys.has(key)) continue;

    const options = binaryOptionElements(block).filter(
      (el) => normalizeSpace(el.innerText).toLowerCase() === desired.toLowerCase()
    );
    if (setRadioChoiceInBlock(block, desired)) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(text, desired, "radio");
      continue;
    }
    if (options.length > 0 && clickElementSafely(options[0])) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(text, desired, "radio");
      continue;
    }

    const clickables = Array.from(
      block.querySelectorAll("label, button, [role='radio'], [role='option'], [tabindex], div, span")
    ).filter((el) => isVisible(el));
    const exact = clickables.find((el) => normalizeSpace(el.innerText).toLowerCase() === desired.toLowerCase());
    if (exact && clickElementSafely(exact)) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(text, desired, "radio");
      continue;
    }
    const prefixed = clickables.find((el) =>
      new RegExp(`^\\s*${desired}\\b`, "i").test(normalizeSpace(el.innerText))
    );
    if (prefixed && clickElementSafely(prefixed)) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(text, desired, "radio");
      continue;
    }
  }

  // Fallback for custom widget trees: infer question context from nearby ancestor text,
  // then click Yes/No labels directly.
  const yesNoOptions = binaryOptionElements(document);
  for (const option of yesNoOptions) {
    const txt = normalizeSpace(option.innerText);
    const lowTxt = txt.toLowerCase();
    const desired = /\byes\b/.test(lowTxt) ? "yes" : /\bno\b/.test(lowTxt) ? "no" : "";
    if (!desired) continue;
    const container =
      option.closest("fieldset, [role='radiogroup'], [role='group'], .application-question, .question, .form-group, section, article, li, div") ||
      option.parentElement;
    const context = normalizeSpace(container?.innerText || "");
    if (!context) continue;
    const want = chooseBooleanByLabel(context, profile || {});
    if (!want || want !== desired) continue;
    const key = `${context.slice(0, 180).toLowerCase()}|${want}`;
    if (clickedKeys.has(key)) continue;
    if (setRadioChoiceInBlock(container || document.body, want === "yes" ? "Yes" : "No")) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(context, want === "yes" ? "Yes" : "No", "radio");
      continue;
    }
    if (clickElementSafely(option)) {
      changed += 1;
      clickedKeys.add(key);
      if (recorder) recorder.add(context, want === "yes" ? "Yes" : "No", "radio");
    }
  }

  return changed;
}

function radioGroupContext(field) {
  const group = field.closest("fieldset, [role='radiogroup'], .application-question, .question, .form-group, div");
  if (!group) return "";
  const text = (group.innerText || "").trim().replace(/\s+/g, " ");
  return text.slice(0, 300).toLowerCase();
}

function findComboboxLabel(box) {
  const id = box.getAttribute("id");
  if (id) {
    const label = document.querySelector(`label[for='${CSS.escape(id)}']`);
    if (label) return normalizeSpace(label.innerText).toLowerCase();
  }
  const ariaLabel = (box.getAttribute("aria-label") || "").toLowerCase();
  if (ariaLabel) return ariaLabel;
  const labelledBy = box.getAttribute("aria-labelledby");
  if (labelledBy) {
    const txt = labelledBy
      .split(/\s+/)
      .filter(Boolean)
      .map((x) => document.getElementById(x))
      .filter(Boolean)
      .map((x) => normalizeSpace(x.innerText))
      .join(" ")
      .toLowerCase();
    if (txt) return txt;
  }
  const nearby = box.closest("fieldset, .form-group, .question, section, div");
  if (!nearby) return "";
  return normalizeSpace(nearby.innerText).slice(0, 250).toLowerCase();
}

function comboboxQuestionContainer(box) {
  return (
    box.closest("fieldset, [role='group'], [role='radiogroup'], .application-question, .question, .form-group, section, article, li, div") ||
    box.parentElement
  );
}

function comboboxOptionsFor(box) {
  const visible = (nodes) => Array.from(nodes).filter((el) => isVisible(el));
  const controlsId = box.getAttribute("aria-controls");
  const labelledBy = box.getAttribute("aria-owns");
  const ids = [controlsId, labelledBy].filter(Boolean);
  for (const id of ids) {
    const list = document.getElementById(id);
    if (list) {
      const scoped = visible(
        list.querySelectorAll("[role='option'], li, button, div[tabindex], span[tabindex], [data-value]")
      );
      if (scoped.length) return scoped;
    }
  }

  const listboxes = visible(
    document.querySelectorAll("[role='listbox'], [id*='listbox'], ul[role='menu'], .select-menu, .dropdown-menu, .menu")
  );
  for (const list of listboxes) {
    const opts = visible(
      list.querySelectorAll("[role='option'], li, button, div[tabindex], span[tabindex], [data-value]")
    );
    if (opts.length) return opts;
  }

  return visible(document.querySelectorAll("[role='option'], li[role='option'], [data-value], .option, .select-option, .menu-item"));
}

function selectOptionInCombobox(box, desiredText, boolHint = "") {
  if (!desiredText) return false;
  const options = comboboxOptionsFor(box).filter((el) => {
    const txt = normalizeSpace(el.innerText);
    if (!txt) return false;
    if (txt.length > 40) return false;
    if (/^select one$/i.test(txt)) return false;
    return true;
  });
  if (!options.length) return false;

  const desired = normalizeChoiceText(desiredText);
  let match = null;
  let bestScore = 0;
  for (const option of options) {
    const score = optionScore(normalizeChoiceText(option.innerText), desired);
    if (score > bestScore) {
      bestScore = score;
      match = option;
    }
  }
  if (!match && boolHint) {
    if (boolHint === "yes") {
      match = options.find((el) => /^(yes|true)$/i.test(normalizeSpace(el.innerText)));
    } else if (boolHint === "no") {
      match = options.find((el) => /^(no|false)$/i.test(normalizeSpace(el.innerText)));
    }
  }
  if (!match || bestScore < 0.5) return false;
  return clickElementSafely(match);
}

function shouldSkipAutofillField(field, contextLabel, nameHint) {
  const placeholder = String(field.getAttribute?.("placeholder") || "").toLowerCase();
  const aria = String(field.getAttribute?.("aria-label") || "").toLowerCase();
  const combined = `${String(contextLabel || "").toLowerCase()} ${String(nameHint || "").toLowerCase()} ${placeholder} ${aria}`.trim();

  // Keep phone extension fields blank unless user explicitly fills them manually.
  if (/\b(phone|mobile|telephone|tel)\b/.test(combined) && /\b(ext|extension|extn|x)\b/.test(combined)) {
    return true;
  }
  return false;
}

function isSkillContext(contextLabel, nameHint, field) {
  const placeholder = String(field?.getAttribute?.("placeholder") || "").toLowerCase();
  const aria = String(field?.getAttribute?.("aria-label") || "").toLowerCase();
  const combined = `${String(contextLabel || "").toLowerCase()} ${String(nameHint || "").toLowerCase()} ${placeholder} ${aria}`.trim();
  return /\bskills?\b|\btechnical skills\b|\btech stack\b|\badd skills\b|\btype to add skills\b/.test(combined);
}

function commitTokenValue(input, value) {
  if (!input || !value) return false;
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(input.__proto__, "value")?.set;
  if (setter) setter.call(input, value);
  else input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  const keyOpts = { bubbles: true, cancelable: true, key: "Enter", code: "Enter", keyCode: 13, which: 13 };
  input.dispatchEvent(new KeyboardEvent("keydown", keyOpts));
  input.dispatchEvent(new KeyboardEvent("keypress", keyOpts));
  input.dispatchEvent(new KeyboardEvent("keyup", keyOpts));
  input.style.outline = "2px solid #0ea5e9";
  return true;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createQuestionBankRecorder() {
  const items = [];
  const seen = new Set();
  return {
    add(question, answer, type = "text") {
      const q = normalizeSpace(question || "").slice(0, 320);
      const a = normalizeSpace(answer || "").slice(0, 180);
      if (!q || !a) return;
      const key = `${canonicalQuestion(q)}|${a.toLowerCase()}|${type}`;
      if (!canonicalQuestion(q) || seen.has(key)) return;
      seen.add(key);
      items.push({ question: q, answer: a, type });
    },
    all() {
      return items;
    },
  };
}

function normalizeMatchText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9+#.\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function scoreSkillMatch(skill, optionText) {
  const s = normalizeMatchText(skill);
  const o = normalizeMatchText(optionText);
  if (!s || !o) return 0;
  if (o === s) return 1;
  if (o.startsWith(s)) return 0.95;
  if (o.includes(s)) return 0.85;
  const sTokens = s.split(" ").filter(Boolean);
  const oTokens = o.split(" ").filter(Boolean);
  if (!sTokens.length || !oTokens.length) return 0;
  let overlap = 0;
  for (const t of sTokens) {
    if (oTokens.includes(t)) overlap += 1;
  }
  return overlap / Math.max(sTokens.length, oTokens.length);
}

function visibleSkillOptionsForInput(input) {
  const visible = (nodes) => Array.from(nodes).filter((el) => isVisible(el));
  const options = [];
  const controls = input.getAttribute("aria-controls");
  if (controls) {
    const root = document.getElementById(controls);
    if (root) {
      options.push(
        ...visible(root.querySelectorAll("[role='option'], li, [data-value], .option, .menu-item, div[tabindex]"))
      );
    }
  }
  if (!options.length) {
    const localRoot =
      input.closest("fieldset, .application-question, .question, .form-group, section, div") || document.body;
    options.push(
      ...visible(
        localRoot.querySelectorAll(
          "[role='listbox'] [role='option'], [role='option'], li[role='option'], ul li, .select-option, .menu-item, [data-value]"
        )
      )
    );
  }
  if (!options.length) {
    options.push(
      ...visible(
        document.querySelectorAll(
          "[role='listbox'] [role='option'], [role='option'], li[role='option'], .select-option, .menu-item, [data-value]"
        )
      )
    );
  }
  return options.filter((el) => {
    const t = normalizeSpace(el.innerText);
    return t && !/^no items\.?$/i.test(t) && !/^select one$/i.test(t);
  });
}

function clearInputValue(input) {
  const setter = Object.getOwnPropertyDescriptor(input.__proto__, "value")?.set;
  if (setter) setter.call(input, "");
  else input.value = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function clickBestSkillOption(option) {
  if (!option || !isVisible(option)) return false;
  const checkbox = option.matches("input[type='checkbox']")
    ? option
    : option.querySelector?.("input[type='checkbox']");
  if (checkbox && !checkbox.checked) {
    return clickElementSafely(checkbox);
  }
  const rowLike =
    option.closest?.("li, [role='option'], .menu-item, .option, div") ||
    option;
  return clickElementSafely(rowLike);
}

async function searchAndSelectSkill(input, skill) {
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(input.__proto__, "value")?.set;
  if (setter) setter.call(input, skill);
  else input.value = skill;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: skill.slice(-1) || "a" }));

  // Let async suggestion list render.
  await sleep(140);

  const options = visibleSkillOptionsForInput(input);
  let best = null;
  let bestScore = 0;
  for (const option of options) {
    const score = scoreSkillMatch(skill, option.innerText || "");
    if (score > bestScore) {
      bestScore = score;
      best = option;
    }
  }
  if (best && bestScore >= 0.45 && clickBestSkillOption(best)) {
    await sleep(60);
    clearInputValue(input);
    return true;
  }

  // If no fuzzy best, select first visible option as user requested.
  if (options.length > 0 && clickBestSkillOption(options[0])) {
    await sleep(60);
    clearInputValue(input);
    return true;
  }

  // Fallback for token widgets that accept Enter for current search value.
  const keyOpts = { bubbles: true, cancelable: true, key: "Enter", code: "Enter", keyCode: 13, which: 13 };
  input.dispatchEvent(new KeyboardEvent("keydown", keyOpts));
  input.dispatchEvent(new KeyboardEvent("keypress", keyOpts));
  input.dispatchEvent(new KeyboardEvent("keyup", keyOpts));
  input.style.outline = "2px solid #0ea5e9";
  await sleep(60);
  clearInputValue(input);
  return true;
}

async function fillSkillsWidgets(profile) {
  const skills = skillValues(profile);
  if (!skills.length) return 0;

  const targets = Array.from(
    document.querySelectorAll("input[type='text'], input[role='combobox'], [role='combobox'], textarea")
  ).filter((el) => {
    if (!isVisible(el)) return false;
    if (el.disabled || el.readOnly) return false;
    const nameHint = `${el.getAttribute("name") || ""} ${el.getAttribute("id") || ""}`.toLowerCase();
    const label = `${labelTextForField(el)} ${nameHint} ${(el.getAttribute("placeholder") || "")}`.toLowerCase();
    const ctx = normalizeSpace(
      `${label} ${el.closest("fieldset, .application-question, .question, .form-group, section, div")?.innerText || ""}`
    )
      .slice(0, 260)
      .toLowerCase();
    return /\bskills?\b|\btechnical skills\b|\btech stack\b|\badd skills\b|\btype to add skills\b/.test(ctx);
  });

  let changed = 0;
  for (const el of targets) {
    const tag = el.tagName.toLowerCase();
    if (tag === "textarea") {
      fillField(el, skills.join(", "));
      changed += 1;
      continue;
    }
    let added = false;
    for (const skill of skills) {
      if (await searchAndSelectSkill(el, skill)) added = true;
    }
    if (added) changed += 1;
  }
  return changed;
}

function fillCustomComboboxes(profile, recorder = null) {
  const boxes = Array.from(
    document.querySelectorAll(
      "[role='combobox'], input[role='combobox'], [aria-haspopup='listbox'], button[aria-haspopup='listbox'], [aria-expanded='false'][aria-haspopup], [aria-expanded='true'][aria-haspopup], [data-automation-id*='dropdown'], [data-automation-id*='select'], [data-automation-id*='combo']"
    )
  ).filter((el) => isVisible(el));

  let changed = 0;
  const OPTIONAL_SIGNALS = /\b(sms|whatsapp|text alert|newsletter|marketing|promotional|recruitment campaign|talent community|contact me|updates|notifications?)\b/i;
  const desiredAnswerForLabel = (labelText, box) => {
    const labelOnly = String(labelText || "").toLowerCase();
    const question = normalizeSpace(comboboxQuestionContainer(box)?.innerText || "").toLowerCase();
    const low = `${labelOnly} ${question}`;
    // Skip optional marketing/consent opt-ins — never auto-fill these
    if (OPTIONAL_SIGNALS.test(labelOnly) || OPTIONAL_SIGNALS.test(question.slice(0, 120))) return "";
    const mapped = mappedDropdownValue(low, profile || {});
    if (mapped) return mapped;
    // Only check state on the direct label, not the full container text (which may contain already-filled field values)
    if (/\bstate\b|\bprovince\b|\bregion\b/.test(labelOnly)) return stateValues(profile)[0] || "";
    const bool = chooseBooleanByLabel(low, profile || {});
    if (bool === "yes") return "Yes";
    if (bool === "no") return "No";
    return "";
  };

  const seenQuestions = new Set();
  for (const box of boxes) {
    const label = findComboboxLabel(box);
    const question = normalizeSpace(comboboxQuestionContainer(box)?.innerText || "").slice(0, 260).toLowerCase();
    if (question && seenQuestions.has(question)) continue;
    const desiredAnswer = desiredAnswerForLabel(label, box);
    if (!desiredAnswer) continue;

    const current = normalizeSpace(box.innerText).toLowerCase();
    if (current.includes(desiredAnswer.toLowerCase())) continue;

    const container = comboboxQuestionContainer(box);
    const localSelect = container?.querySelector?.("select");
    if (localSelect && fillSelectField(localSelect, desiredAnswer)) {
      changed += 1;
      if (recorder) recorder.add(question || label, desiredAnswer, "select");
      if (question) seenQuestions.add(question);
      continue;
    }

    if (!clickElementSafely(box)) continue;
    const boolHint = chooseBooleanByLabel(`${label} ${question}`, profile || {});
    if (selectOptionInCombobox(box, desiredAnswer, boolHint)) {
      changed += 1;
      if (recorder) recorder.add(question || label, desiredAnswer, "select");
      if (question) seenQuestions.add(question);
    }
  }
  return changed;
}

async function fillWorkdayQuestionDropdowns(profile, recorder = null) {
  const questionBlocks = Array.from(
    document.querySelectorAll("fieldset, .application-question, .question, .form-group, section, div")
  ).filter((el) => {
    if (!isVisible(el)) return false;
    const text = normalizeSpace(el.innerText).toLowerCase();
    return /\?$/.test(text) || /eligible to work|sponsorship|work visa|authorized/i.test(text);
  });

  const clicked = new Set();
  let changed = 0;

  for (const block of questionBlocks) {
    const questionText = normalizeSpace(block.innerText).slice(0, 300);
    if (!questionText) continue;
    const desired =
      mappedDropdownValue(questionText, profile || {}) ||
      (() => {
        const yn = chooseBooleanByLabel(questionText, profile || {});
        if (yn === "yes") return "Yes";
        if (yn === "no") return "No";
        return "";
      })();
    if (!desired) continue;

    const key = `${normalizeLookupText(questionText)}|${desired.toLowerCase()}`;
    if (clicked.has(key)) continue;

    const triggerCandidates = Array.from(
      block.querySelectorAll("button, [role='button'], [role='combobox'], [aria-haspopup='listbox'], div, span")
    ).filter((el) => {
      if (!isVisible(el)) return false;
      const txt = normalizeSpace(el.innerText).toLowerCase();
      if (txt === "select one" || txt.startsWith("select one ")) return true;
      if (/dropdown|select|combo|prompt/i.test(String(el.getAttribute("data-automation-id") || ""))) return true;
      const expanded = el.getAttribute("aria-expanded");
      return expanded === "false" || expanded === "true";
    });
    if (!triggerCandidates.length) continue;

    const trigger = triggerCandidates[0];
    if (!clickElementSafely(trigger)) continue;
    await sleep(120);

    const optionPools = [
      document.querySelectorAll("[role='option']"),
      document.querySelectorAll("[role='listbox'] li"),
      document.querySelectorAll("li"),
      document.querySelectorAll("div[tabindex], button"),
    ];
    let options = [];
    for (const pool of optionPools) {
      options = Array.from(pool).filter((el) => {
        if (!isVisible(el)) return false;
        const txt = normalizeSpace(el.innerText);
        if (!txt || txt.length > 60) return false;
        if (/^select one$/i.test(txt)) return false;
        return true;
      });
      if (options.length) break;
    }
    if (!options.length) continue;

    const desiredLow = desired.toLowerCase();
    let best =
      options.find((el) => normalizeSpace(el.innerText).toLowerCase() === desiredLow) ||
      options.find((el) => new RegExp(`^${desiredLow}\\b|\\b${desiredLow}$`, "i").test(normalizeSpace(el.innerText)));
    if (!best) {
      best = options.find((el) => /^(yes|true)$/i.test(normalizeSpace(el.innerText))) && desiredLow === "yes"
        ? options.find((el) => /^(yes|true)$/i.test(normalizeSpace(el.innerText)))
        : best;
      best = options.find((el) => /^(no|false)$/i.test(normalizeSpace(el.innerText))) && desiredLow === "no"
        ? options.find((el) => /^(no|false)$/i.test(normalizeSpace(el.innerText)))
        : best;
    }
    if (!best) continue;
    if (clickElementSafely(best)) {
      changed += 1;
      if (recorder) recorder.add(questionText, desired, "select");
      clicked.add(key);
      await sleep(90);
    }
  }
  return changed;
}

function fillRadioOrCheckbox(field, label, profile) {
  const type = (field.type || "").toLowerCase();
  const context = normalizeChoiceText(
    `${label} ${field.value || ""} ${field.innerText || ""} ${field.getAttribute?.("aria-label") || ""} ${
      field.getAttribute?.("name") || ""
    } ${field.getAttribute?.("id") || ""}`
  );
  const boolChoice = chooseBooleanByLabel(context, profile);

  if (type === "checkbox") {
    const requiredSignals = /i agree|agree to|terms|privacy|policy|consent|certify|attest|acknowledge|voluntary self identify|eeo|equal opportunity|truthful|accurate/;
    const optionalSignals = /newsletter|marketing|promotional|sms|text alerts|job alerts|talent community|contact me|updates/;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
    if (requiredSignals.test(context) && !optionalSignals.test(context)) {
      if (!field.checked) {
        if (setter) setter.call(field, true);
        else field.checked = true;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
        field.click();
      }
      field.style.outline = "2px solid #0ea5e9";
      return true;
    }
    if (boolChoice === "yes" || boolChoice === "no") {
      const target = boolChoice === "yes";
      if (field.checked !== target) {
        if (setter) setter.call(field, target);
        else field.checked = target;
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
        field.click();
      }
      field.style.outline = "2px solid #0ea5e9";
      return true;
    }
    return false;
  }

  if (!boolChoice) return false;
  const isYesChoice = /(yes|true|authorized|eligible|y)/.test(context);
  const isNoChoice = /(no|false|not|n)/.test(context);
  const shouldSelect = (boolChoice === "yes" && isYesChoice) || (boolChoice === "no" && isNoChoice);
  if (!shouldSelect) return false;

  if (type === "radio") {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "checked")?.set;
    if (setter) setter.call(field, true);
    else field.checked = true;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    field.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
  } else {
    if (typeof field.click === "function") field.click();
  }
  field.style.outline = "2px solid #0ea5e9";
  return true;
}

function fillAriaCheckboxes(profile) {
  const boxes = Array.from(document.querySelectorAll("[role='checkbox']")).filter((el) => isVisible(el));
  let changed = 0;
  for (const box of boxes) {
    const state = (box.getAttribute("aria-checked") || "").toLowerCase();
    if (state === "true") continue;
    const label = normalizeSpace(
      `${box.innerText || ""} ${box.getAttribute("aria-label") || ""} ${box.closest("label, fieldset, .question, .form-group")?.innerText || ""}`
    ).toLowerCase();
    const requiredSignals = /i agree|agree to|terms|privacy|policy|consent|certify|attest|acknowledge|truthful|accurate|voluntary self identify|eeo/;
    const optionalSignals = /newsletter|marketing|promotional|sms|text alerts|talent community|contact me|updates/;
    const boolChoice = chooseBooleanByLabel(label, profile || {});
    if (requiredSignals.test(label) && !optionalSignals.test(label)) {
      if (clickElementSafely(box)) changed += 1;
      continue;
    }
    if (boolChoice === "yes" && clickElementSafely(box)) changed += 1;
  }
  return changed;
}

function fillAriaSwitches(profile) {
  const switches = Array.from(document.querySelectorAll("[role='switch']")).filter((el) => isVisible(el));
  let changed = 0;
  for (const sw of switches) {
    const context = normalizeSpace(
      `${sw.innerText || ""} ${sw.getAttribute("aria-label") || ""} ${sw.closest("label, fieldset, .question, .form-group")?.innerText || ""}`
    ).toLowerCase();
    const boolChoice = chooseBooleanByLabel(context, profile || {});
    if (!boolChoice) continue;
    const checked = (sw.getAttribute("aria-checked") || "").toLowerCase() === "true";
    const target = boolChoice === "yes";
    if (checked === target) continue;
    if (clickElementSafely(sw)) changed += 1;
  }
  return changed;
}

function fillExperienceSections(profile, recorder = null) {
  const exps = Array.isArray(profile.workExperiences) ? profile.workExperiences : [];
  if (!exps.length) return 0;
  let filled = 0;

  // Collect all editable inputs
  const allInputs = Array.from(
    document.querySelectorAll("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select")
  ).filter((el) => isVisible(el) && !el.disabled && !el.readOnly);

  // Group inputs by experience-index from their name attribute (e.g. work_experiences[0][company])
  const atsPrefixes = ["work_experience", "work_experiences", "employment", "employer", "job_history"];
  const buckets = {};
  for (const field of allInputs) {
    const name = (field.getAttribute("name") || "").toLowerCase();
    if (!name) continue;
    if (!atsPrefixes.some((p) => name.includes(p))) continue;
    const idxMatch = name.match(/\[(\d+)\]/) || name.match(/_(\d+)_/);
    const idx = idxMatch ? parseInt(idxMatch[1], 10) : 0;
    (buckets[idx] = buckets[idx] || []).push(field);
  }

  for (const [idxStr, fields] of Object.entries(buckets)) {
    const exp = exps[parseInt(idxStr, 10)] || exps[0] || {};
    for (const field of fields) {
      if (hasMeaningfulExistingValue(field)) continue;
      const name = (field.getAttribute("name") || "").toLowerCase();
      const lbl = labelTextForField(field).toLowerCase();
      const combined = `${name} ${lbl}`;
      let value = "";
      if (/company|employer|organization/.test(combined)) value = exp.company || "";
      else if (/title|position|role/.test(combined) && !/role family/.test(combined)) value = exp.title || "";
      else if (/\bstart\b/.test(combined) && /date|month|year/.test(combined)) value = exp.startDate || "";
      else if (/\bend\b/.test(combined) && /date|month|year/.test(combined)) value = exp.endDate || "Present";
      else if (/description|responsibilit|duties/.test(combined)) value = exp.description || "";
      if (!value) continue;
      if (field.tagName.toLowerCase() === "select") { fillSelectField(field, value); }
      else { fillField(field, value); }
      filled++;
      if (recorder) recorder.add(lbl || name, value, "text");
    }
  }

  // Also handle standalone "Current Employer / Most Recent Employer" labels
  for (const field of allInputs) {
    if (hasMeaningfulExistingValue(field)) continue;
    const lbl = labelTextForField(field).toLowerCase();
    const nameId = `${field.getAttribute("name") || ""} ${field.getAttribute("id") || ""}`.toLowerCase();
    const combined = `${lbl} ${nameId}`.trim();
    const isPrev = /\bprevious\b|\bformer\b|\bprior\b|\bpast\b/.test(combined);
    const expEntry = isPrev ? (exps[1] || {}) : (exps[0] || {});
    let value = "";
    if (/\bcurrent employer\b|\bmost recent employer\b|\bprevious employer\b/.test(combined)) value = expEntry.company || "";
    else if (/\bcurrent (job )?title\b|\bcurrent position\b|\bmost recent (job )?title\b/.test(combined)) value = expEntry.title || "";
    if (!value) continue;
    fillField(field, value);
    filled++;
    if (recorder) recorder.add(lbl || nameId, value, "text");
  }

  return filled;
}

function fillEducationSections(profile, recorder = null) {
  const edu = Array.isArray(profile.education) ? profile.education : [];
  if (!edu.length) return 0;
  let filled = 0;

  const allInputs = Array.from(
    document.querySelectorAll("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select")
  ).filter((el) => isVisible(el) && !el.disabled && !el.readOnly);

  const edPrefixes = ["education", "academic", "school_name", "university", "college", "degree_name"];
  for (const field of allInputs) {
    const name = (field.getAttribute("name") || "").toLowerCase();
    if (!name) continue;
    if (!edPrefixes.some((p) => name.includes(p))) continue;
    if (hasMeaningfulExistingValue(field)) continue;
    const lbl = labelTextForField(field).toLowerCase();
    const combined = `${name} ${lbl}`;
    const edu0 = edu[0] || {};
    let value = "";
    if (/school|university|college|institution/.test(combined)) value = edu0.school || profile.educationSchool || "";
    else if (/\bdegree\b/.test(combined)) value = edu0.degree || profile.educationDegree || "";
    else if (/field|major|program|concentration/.test(combined) && !/field of work/.test(combined)) value = edu0.field || profile.educationField || "";
    else if (/\bgpa\b|\bgrade/.test(combined)) value = edu0.gpa || profile.educationGpa || "";
    else if (/grad(uation)? year|end year|class of/.test(combined)) value = edu0.endYear || profile.educationEndYear || "";
    else if (/start year/.test(combined)) value = edu0.startYear || profile.educationStartYear || "";
    if (!value) continue;
    if (field.tagName.toLowerCase() === "select") { fillSelectField(field, value); }
    else { fillField(field, value); }
    filled++;
    if (recorder) recorder.add(lbl || name, value, "text");
  }
  return filled;
}

async function safePrefill(profile, options = {}) {
  const platform = detectPlatform();
  const captchaPresent = detectCaptcha();
  const forceRefill = Boolean(options.forceRefill);
  const qbRecorder = createQuestionBankRecorder();

  const fields = Array.from(
    document.querySelectorAll(
      "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select, [role='radio']"
    )
  );
  let filledCount = 0;
  const warnings = [];
  const seenRadioNames = new Set();
  let candidateFields = 0;
  let coverLetterFilled = false;
  const aiFieldMode = Boolean(options.aiFieldMode);
  let aiFilledCount = 0;
  if (captchaPresent) {
    warnings.push("CAPTCHA detected. Continuing with partial prefill only; CAPTCHA and submission remain manual.");
  }

  for (const field of fields) {
    if (field.disabled || field.readOnly) continue;
    candidateFields += 1;
    const type = (field.type || "").toLowerCase();
    const isRoleRadio = (field.getAttribute && field.getAttribute("role") === "radio");
    if (isRoleRadio && field.getAttribute("aria-checked") === "true") {
      continue;
    }

    const nameHint = `${field.getAttribute("name") || ""} ${field.getAttribute("id") || ""}`.toLowerCase();
    const label = `${labelTextForField(field)} ${nameHint}`.trim();
    const contextLabel =
      label ||
      localQuestionForField(field) ||
      normalizeSpace(
        field.closest("fieldset, [role='group'], .application-question, .question, .form-group, section, div")?.innerText || ""
      )
        .slice(0, 280)
        .toLowerCase();
    if (!contextLabel) continue;
    if (shouldSkipAutofillField(field, contextLabel, nameHint)) continue;
    if (isSkillContext(contextLabel, nameHint, field)) {
      // Skills are handled by dedicated one-by-one selector logic later.
      continue;
    }

    if (!forceRefill && type !== "radio" && type !== "checkbox") {
      const mapped = mappedDropdownValue(contextLabel, profile || {});
      const yn = chooseBooleanByLabel(contextLabel, profile || {});
      const forceDesired = mapped || (yn === "yes" ? "Yes" : yn === "no" ? "No" : "");
      if (hasMeaningfulExistingValue(field)) {
        const current = normalizeSpace(field.value || field.innerText || "").toLowerCase();
        if (forceDesired && !current.includes(forceDesired.toLowerCase())) {
          // continue with overwrite path below
        } else {
          // Already set (or no better signal) - count as matched to avoid false warning.
          filledCount += 1;
          continue;
        }
      }
    }

    if (type === "radio" || type === "checkbox" || isRoleRadio) {
      if (type === "radio") {
        const groupName = field.name || field.id || label;
        if (seenRadioNames.has(groupName)) continue;
        const group = fields.filter(
          (f) => (f.type || "").toLowerCase() === "radio" && (f.name || f.id || "") === (field.name || field.id || "")
        );
        let clicked = false;
        for (const item of group) {
          const itemLabel = `${labelTextForField(item)} ${(item.value || "")} ${(item.id || "")} ${(item.name || "")}`.toLowerCase();
          const context = `${contextLabel} ${radioGroupContext(item)} ${itemLabel}`.trim();
          if (fillRadioOrCheckbox(item, context, profile || {})) {
            filledCount += 1;
            clicked = true;
            break;
          }
        }
        seenRadioNames.add(groupName);
        if (!clicked && /authorization|authorized|sponsorship/.test(contextLabel)) {
          warnings.push(`Could not confidently select radio option for: ${label}`);
        }
      } else if (isRoleRadio) {
        const container = field.closest("[role='radiogroup'], fieldset, .application-question, .question, .form-group, div");
        const group = container
          ? Array.from(container.querySelectorAll("[role='radio']"))
          : fields.filter((f) => f.getAttribute && f.getAttribute("role") === "radio");
        let clicked = false;
        for (const item of group) {
          const itemLabel = `${labelTextForField(item)} ${(item.innerText || "")} ${(item.getAttribute("aria-label") || "")}`.toLowerCase();
          const context = `${contextLabel} ${radioGroupContext(item)} ${itemLabel}`.trim();
          if (fillRadioOrCheckbox(item, context, profile || {})) {
            filledCount += 1;
            clicked = true;
            break;
          }
        }
        if (!clicked && /authorization|authorized|sponsorship|primary residence|salary/i.test(contextLabel)) {
          warnings.push(`Could not confidently select custom radio option for: ${label}`);
        }
      } else if (fillRadioOrCheckbox(field, contextLabel, profile || {})) {
        filledCount += 1;
      }
      continue;
    }

    if (field.tagName.toLowerCase() === "select") {
      const mapped = mappedDropdownValue(contextLabel, profile || {});
      const custom = customAnswerForQuestion(contextLabel, profile || {});
      const value =
        mapped ||
        custom ||
        mapProfileToField(contextLabel, profile || {}) ||
        mapProfileByPlatform(field, profile || {}, platform) ||
        mapProfileToNameOrId(field, profile || {}) ||
        chooseBooleanByLabel(contextLabel, profile || {});
      if (value && fillSelectField(field, value)) {
        filledCount += 1;
        qbRecorder.add(contextLabel, value, "select");
      } else if (/authorization|authorized|sponsorship/.test(contextLabel)) {
        warnings.push(`Could not match select options for: ${label}`);
      }
      continue;
    }

    if (field.tagName.toLowerCase() === "textarea") {
      let txt = "";
      if (/cover letter/.test(contextLabel)) {
        txt = String(options.coverLetterText || "").trim();
      } else if (/salary range|desired salary|compensation|current ctc|expected ctc|pay range/.test(contextLabel)) {
        txt = String(profile?.desiredSalaryRange || "").trim();
      } else {
        txt = String(customAnswerForQuestion(contextLabel, profile || {}) || "").trim();
      }
      if (txt) {
        fillField(field, txt);
        if (/cover letter/.test(contextLabel)) coverLetterFilled = true;
        filledCount += 1;
        qbRecorder.add(contextLabel, txt, "text");
        continue;
      }
    }

    const value =
      mappedDropdownValue(contextLabel, profile || {}) ||
      customAnswerForQuestion(contextLabel, profile || {}) ||
      mapProfileToField(contextLabel, profile || {}) ||
      mapProfileByPlatform(field, profile || {}, platform) ||
      mapProfileToNameOrId(field, profile || {});
    let resolved = value;
    if (!resolved && aiFieldMode) {
      const guess = aiScoreField(field, profile || {});
      if (guess.value && guess.score >= 0.62) {
        resolved = guess.value;
        aiFilledCount += 1;
      } else if (guess.score >= 0.45) {
        warnings.push(`AI mapper skipped low-confidence field: ${label || guess.key}`);
      }
    }
    if (!resolved) continue;

    const ambiguous = label.includes("name") && !label.includes("first") && !label.includes("last") && !label.includes("full");
    if (ambiguous && !(profile.fullName || "")) {
      warnings.push("Skipped ambiguous name field.");
      continue;
    }
    fillField(field, resolved);
    filledCount += 1;
    if (/(authorized|authorization|sponsorship|salary|eligible|visa|residence|agreement|older)/i.test(contextLabel)) {
      qbRecorder.add(contextLabel, resolved, "text");
    }
  }

  const blockAnswers = answerQuestionBlocks(profile || {}, qbRecorder);
  if (blockAnswers > 0) {
    filledCount += blockAnswers;
  }

  const ariaCheckboxes = fillAriaCheckboxes(profile || {});
  if (ariaCheckboxes > 0) {
    filledCount += ariaCheckboxes;
  }

  const ariaSwitches = fillAriaSwitches(profile || {});
  if (ariaSwitches > 0) {
    filledCount += ariaSwitches;
  }

  const customSelects = fillCustomComboboxes(profile || {}, qbRecorder);
  if (customSelects > 0) {
    filledCount += customSelects;
  }

  if (platform === "workday") {
    const workdaySelects = await fillWorkdayQuestionDropdowns(profile || {}, qbRecorder);
    if (workdaySelects > 0) {
      filledCount += workdaySelects;
    }
  }

  const skillsFilled = await fillSkillsWidgets(profile || {});
  if (skillsFilled > 0) {
    filledCount += skillsFilled;
  }

  const expFilled = fillExperienceSections(profile || {}, qbRecorder);
  if (expFilled > 0) filledCount += expFilled;

  const eduFilled = fillEducationSections(profile || {}, qbRecorder);
  if (eduFilled > 0) filledCount += eduFilled;

  if (candidateFields === 0) {
    const iframeCount = document.querySelectorAll("iframe").length;
    if (iframeCount > 0) {
      warnings.push("No editable fields in top page. Form may be inside iframe and inaccessible to extension.");
    } else {
      warnings.push("No editable fields detected on this page.");
    }
  } else if (filledCount === 0) {
    warnings.push(`Detected fields on ${platform} page but none matched saved profile keys. Check Options profile and field labels.`);
  }

  const fileInputs = Array.from(document.querySelectorAll("input[type='file']")).filter((f) => !f.disabled);
  if (fileInputs.length > 0) {
    fileInputs.forEach((f) => {
      f.style.outline = "2px solid #f59e0b";
      f.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    if (options.assistUploads) {
      const firstVisible = fileInputs.find((f) => {
        const rect = f.getBoundingClientRect();
        const style = window.getComputedStyle(f);
        return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
      });
      if (firstVisible) {
        firstVisible.click();
        warnings.push(
          "Opened file picker for upload. Select generated resume/cover files from your configured Documents packet folder."
        );
      } else {
        const uploadButton = Array.from(document.querySelectorAll("button, [role='button'], a, div[tabindex]"))
          .filter((el) => isVisible(el))
          .find((el) => /upload|attach|resume|cv|cover letter|add file|browse/i.test(normalizeSpace(el.innerText)));
        if (uploadButton && clickElementSafely(uploadButton)) {
          warnings.push("Opened upload control. Select generated files from your configured Documents packet folder.");
        } else {
          warnings.push("File upload fields detected but not directly visible. Upload manually.");
        }
      }
    }
  }

  if (aiFieldMode && aiFilledCount > 0) {
    warnings.push(`AI field mapper filled ${aiFilledCount} additional fields.`);
  }

  return { filledCount, warnings, platform, learnedQuestions: qbRecorder.all() };
}

function assistUpload(kind) {
  const fileInputs = Array.from(document.querySelectorAll("input[type='file']")).filter((f) => !f.disabled);
  if (!fileInputs.length) {
    return { warnings: ["No file upload field found on this page."] };
  }

  const targetTerms =
    kind === "cover_letter"
      ? ["cover", "cover letter", "motivation", "additional document"]
      : ["resume", "cv", "curriculum vitae"];

  const scored = fileInputs.map((input) => {
    const hint = `${labelTextForField(input)} ${(input.getAttribute("name") || "")} ${(input.getAttribute("id") || "")} ${(input.getAttribute("aria-label") || "")}`.toLowerCase();
    let score = 0;
    for (const term of targetTerms) {
      if (hint.includes(term)) score += term.length > 4 ? 2 : 1;
    }
    return { input, score, hint };
  });

  scored.sort((a, b) => b.score - a.score);
  const target = scored[0]?.input || fileInputs[0];
  if (!target) {
    return { warnings: ["Upload target not found."] };
  }

  target.style.outline = "2px solid #f59e0b";
  target.scrollIntoView({ block: "center", behavior: "smooth" });
  target.click();
  return {
    warnings: [
      kind === "cover_letter"
        ? "Cover letter picker opened. Choose the generated cover letter PDF."
        : "Resume picker opened. Choose the generated resume PDF.",
    ],
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "extract_job") {
    if (message.requireTop && window.top !== window) {
      return false;
    }
    const structured = structuredJobPosting();
    let text = cleanExtractedJobText(structured.description);
    if (!looksLikeJobDescription(text)) text = cleanExtractedJobText(extractBySelectors());
    if (!looksLikeJobDescription(text)) text = cleanExtractedJobText(fallbackVisibleText());
    if (!looksLikeJobDescription(text)) text = "";
    const headingTitle = visibleJobTitle();
    const headingCompany = companyFromJobTitle(
      Array.from(document.querySelectorAll("main h1, article h1, h1"))
        .map((node) => textFromElement(node))
        .find((value) => /\s+at\s+/i.test(value)) || ""
    );
    const payload = {
      pageTitle: document.title || "",
      jobTitle: headingTitle || cleanExtractedJobTitle(structured.title),
      company: structured.company || headingCompany || metadataCompany(),
      url: location.href,
      jobText: smartTrim(text || ""),
      captchaDetected: detectCaptcha()
    };
    sendResponse(payload);
    return true;
  }

  if (message.type === "prefill_form") {
    safePrefill(message.profile || {}, message)
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ filledCount: 0, warnings: [String(err?.message || err)], platform: detectPlatform() }));
    return true;
  }

  if (message.type === "assist_upload") {
    const result = assistUpload(message.kind || "resume");
    sendResponse(result);
    return true;
  }

  if (message.type === "extract_linkedin_contacts") {
    const result = extractLinkedinContactsFromVisiblePage();
    sendResponse(result);
    return true;
  }

  return false;
});
