const fields = [
  "apiBaseUrl",
  "websiteUrl",
  "extensionToken",
  "jacToken",
  "openaiApiKey",
  "rememberOpenAiKey",
  "fullName",
  "firstName",
  "lastName",
  "email",
  "phone",
  "linkedin",
  "github",
  "portfolio",
  "location",
  "state",
  "workAuthorization",
  "sponsorship",
  "salaryInRange",
  "age18Plus",
  "employmentRestriction",
  "desiredSalaryRange",
  "skillsList",
  "baseResumeBulletIds",
  "customQa",
  "dropdownMap",
  "questionBank",
  // EEO & Demographics
  "preferredName",
  "gender",
  "pronouns",
  "hispanicOrLatino",
  "raceEthnicity",
  "veteranStatus",
  "disabilityStatus",
  // Address by region
  "addressLine1NjNy",
  "cityNjNy",
  "stateNjNy",
  "zipNjNy",
  "addressLine1Ca",
  "cityCa",
  "stateCa",
  "zipCa",
  // Education & Experience (stored as JSON text)
  "educationJson",
  "workExperiencesJson",
];

const DEFAULT_EDUCATION = [
  {
    degree: "M.S.",
    field: "Data Science",
    school: "Stevens Institute of Technology",
    gpa: "3.82",
    startYear: "2024",
    endYear: "2026",
  },
];

const DEFAULT_EXPERIENCES = [
  {
    company: "LTIMindtree",
    title: "Data Engineer",
    startDate: "Sep 2020",
    endDate: "Feb 2023",
    location: "Mumbai, India",
    description:
      "Designed and stabilized SAP CPI data pipelines and enterprise integrations using Python, SQL, SAP S/4HANA, and Salesforce, improving reconciliation and operational visibility.",
  },
  {
    company: "Accenture",
    title: "Application Development Analyst",
    startDate: "Jul 2020",
    endDate: "Dec 2022",
    location: "Mumbai, India",
    description:
      "Developed machine learning models and NLP pipelines for enterprise clients using Python, TensorFlow, and Spark. Implemented production data science applications and predictive analytics solutions.",
  },
];

function parseJsonArray(text) {
  try {
    const parsed = JSON.parse(String(text || "").trim() || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function getValue(id) {
  return document.getElementById(id).value.trim();
}

function setValue(id, value) {
  document.getElementById(id).value = value || "";
}

function parseCustomQaLines(text) {
  const lines = String(text || "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
  const out = [];
  for (const line of lines) {
    const idx = line.indexOf("=>");
    if (idx <= 0) continue;
    const question = line.slice(0, idx).trim();
    const answer = line.slice(idx + 2).trim();
    if (!question || !answer) continue;
    out.push({ question, answer });
  }
  return out;
}

function serializeCustomQaLines(items) {
  const rows = Array.isArray(items) ? items : [];
  return rows
    .filter((x) => x && x.question && x.answer)
    .map((x) => `${x.question} => ${x.answer}`)
    .join("\n");
}

function parseKeyValueLines(text) {
  const lines = String(text || "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
  const out = [];
  for (const line of lines) {
    const idx = line.indexOf("=>");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 2).trim();
    if (!key || !value) continue;
    out.push({ key, value });
  }
  return out;
}

function serializeKeyValueLines(items) {
  const rows = Array.isArray(items) ? items : [];
  return rows
    .filter((x) => x && x.key && x.value)
    .map((x) => `${x.key} => ${x.value}`)
    .join("\n");
}

async function loadSettings() {
  const stored = await chrome.storage.local.get({
    apiBaseUrl: "http://127.0.0.1:8787",
    websiteUrl: "http://localhost:3000/app/jobs",
    extensionToken: "",
    jacToken: "",
    openaiApiKey: "",
    rememberOpenAiKey: false,
    profile: {},
    baseResumeBulletIds: ""
  });
  const sessionStored = await chrome.storage.session?.get({ openaiApiKey: "" }).catch(() => ({ openaiApiKey: "" })) || { openaiApiKey: "" };
  setValue("apiBaseUrl", stored.apiBaseUrl);
  setValue("websiteUrl", stored.websiteUrl);
  setValue("extensionToken", stored.extensionToken);
  setValue("jacToken", stored.jacToken);
  setValue("openaiApiKey", sessionStored.openaiApiKey || stored.openaiApiKey || "");
  document.getElementById("rememberOpenAiKey").checked = Boolean(stored.rememberOpenAiKey);
  setValue("baseResumeBulletIds", stored.baseResumeBulletIds || "");

  const profile = stored.profile || {};
  [
    "fullName",
    "firstName",
    "lastName",
    "email",
    "phone",
    "linkedin",
    "github",
    "portfolio",
    "location",
    "state",
    "workAuthorization",
    "sponsorship",
    "salaryInRange",
    "age18Plus",
    "employmentRestriction",
    "desiredSalaryRange",
    "skillsList",
  ].forEach((k) => setValue(k, profile[k] || ""));
  setValue("customQa", serializeCustomQaLines(profile.customQa || []));
  setValue("dropdownMap", serializeKeyValueLines(profile.dropdownMap || []));
  setValue("questionBank", serializeCustomQaLines(profile.questionBank || []));

  // EEO & Demographics — seed defaults on first use
  setValue("preferredName", profile.preferredName || "Venkatesh Mudaliar");
  setValue("gender", profile.gender || "Male");
  setValue("pronouns", profile.pronouns || "He/Him");
  setValue("hispanicOrLatino", profile.hispanicOrLatino || "No");
  setValue("raceEthnicity", profile.raceEthnicity || "Asian");
  setValue("veteranStatus", profile.veteranStatus || "I am not a protected veteran");
  setValue("disabilityStatus", profile.disabilityStatus || "No, I don't have a disability");

  // Address by region
  setValue("addressLine1NjNy", profile.addressLine1NjNy || "");
  setValue("cityNjNy", profile.cityNjNy || "");
  setValue("stateNjNy", profile.stateNjNy || "");
  setValue("zipNjNy", profile.zipNjNy || "");
  setValue("addressLine1Ca", profile.addressLine1Ca || "1883 Mount Conness Way");
  setValue("cityCa", profile.cityCa || "Antioch");
  setValue("stateCa", profile.stateCa || "CA");
  setValue("zipCa", profile.zipCa || "94531");

  // Education & Experience JSON
  const eduArr = profile.education || [];
  setValue("educationJson", JSON.stringify(eduArr.length ? eduArr : DEFAULT_EDUCATION, null, 2));
  const expArr = profile.workExperiences || [];
  setValue("workExperiencesJson", JSON.stringify(expArr.length ? expArr : DEFAULT_EXPERIENCES, null, 2));
}

async function saveSettings() {
  const profile = {
    fullName: getValue("fullName"),
    firstName: getValue("firstName"),
    lastName: getValue("lastName"),
    email: getValue("email"),
    phone: getValue("phone"),
    linkedin: getValue("linkedin"),
    github: getValue("github"),
    portfolio: getValue("portfolio"),
    location: getValue("location"),
    state: getValue("state"),
    workAuthorization: getValue("workAuthorization"),
    sponsorship: getValue("sponsorship"),
    salaryInRange: getValue("salaryInRange"),
    age18Plus: getValue("age18Plus"),
    employmentRestriction: getValue("employmentRestriction"),
    desiredSalaryRange: getValue("desiredSalaryRange"),
    skillsList: getValue("skillsList"),
    customQa: parseCustomQaLines(getValue("customQa")),
    dropdownMap: parseKeyValueLines(getValue("dropdownMap")),
    questionBank: parseCustomQaLines(getValue("questionBank")),
    // EEO & Demographics
    preferredName: getValue("preferredName"),
    gender: getValue("gender"),
    pronouns: getValue("pronouns"),
    hispanicOrLatino: getValue("hispanicOrLatino"),
    raceEthnicity: getValue("raceEthnicity"),
    veteranStatus: getValue("veteranStatus"),
    disabilityStatus: getValue("disabilityStatus"),
    // Address by region
    addressLine1NjNy: getValue("addressLine1NjNy"),
    cityNjNy: getValue("cityNjNy"),
    stateNjNy: getValue("stateNjNy"),
    zipNjNy: getValue("zipNjNy"),
    addressLine1Ca: getValue("addressLine1Ca"),
    cityCa: getValue("cityCa"),
    stateCa: getValue("stateCa"),
    zipCa: getValue("zipCa"),
    // Education & Experience (parsed from JSON textarea)
    education: parseJsonArray(getValue("educationJson")),
    workExperiences: parseJsonArray(getValue("workExperiencesJson")),
  };

  const openaiApiKey = getValue("openaiApiKey");
  const rememberOpenAiKey = Boolean(document.getElementById("rememberOpenAiKey").checked);
  const localPayload = {
    apiBaseUrl: getValue("apiBaseUrl") || "http://127.0.0.1:8787",
    websiteUrl: getValue("websiteUrl") || "http://localhost:3000/app/jobs",
    extensionToken: getValue("extensionToken"),
    jacToken: getValue("jacToken"),
    profile,
    baseResumeBulletIds: getValue("baseResumeBulletIds"),
    rememberOpenAiKey,
  };
  if (rememberOpenAiKey) {
    localPayload.openaiApiKey = openaiApiKey;
    await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  } else {
    localPayload.openaiApiKey = "";
    await chrome.storage.session?.set({ openaiApiKey }).catch(() => {});
  }

  await chrome.storage.local.set(localPayload);

  document.getElementById("status").textContent = "Saved.";
}

document.getElementById("saveBtn").addEventListener("click", saveSettings);
document.getElementById("removeOpenAiKeyBtn").addEventListener("click", async () => {
  setValue("openaiApiKey", "");
  document.getElementById("rememberOpenAiKey").checked = false;
  await chrome.storage.local.set({ openaiApiKey: "", rememberOpenAiKey: false });
  await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  document.getElementById("status").textContent = "API key removed from this extension.";
});
document.getElementById("testOpenAiKeyBtn").addEventListener("click", async () => {
  const key = getValue("openaiApiKey");
  if (!key) {
    document.getElementById("status").textContent = "Paste an API key before testing.";
    return;
  }
  const apiBase = (getValue("apiBaseUrl") || "http://127.0.0.1:8787").replace(/\/+$/, "");
  try {
    const res = await fetch(`${apiBase}/ai/test_key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-OpenAI-API-Key": key,
      },
    });
    const data = await res.json().catch(() => ({}));
    document.getElementById("status").textContent = res.ok ? data.message || "API key works." : data.detail || "API key test failed.";
  } catch {
    document.getElementById("status").textContent = "Could not reach the API server to test the key.";
  }
});
loadSettings();
