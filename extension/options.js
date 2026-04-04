const fields = [
  "jacToken",
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
];

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
  const stored = await chrome.storage.local.get({ jacToken: "", profile: {}, baseResumeBulletIds: "" });
  setValue("jacToken", stored.jacToken);
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
  };

  await chrome.storage.local.set({
    jacToken: getValue("jacToken"),
    profile,
    baseResumeBulletIds: getValue("baseResumeBulletIds"),
  });

  document.getElementById("status").textContent = "Saved.";
}

document.getElementById("saveBtn").addEventListener("click", saveSettings);
loadSettings();
