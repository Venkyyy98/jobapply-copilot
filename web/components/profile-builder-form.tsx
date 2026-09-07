"use client";

import { useState } from "react";
import type { FormEvent } from "react";

type Bullet = {
  id?: string;
  text: string;
};

type Experience = {
  id?: string;
  company: string;
  role: string;
  start_date: string;
  end_date: string;
  location: string;
  bullets: Bullet[];
};

type Education = {
  id?: string;
  school: string;
  degree: string;
  field: string;
  start_date: string;
  end_date: string;
  graduation_date: string;
  gpa: string;
  location: string;
};

type Project = {
  id?: string;
  name: string;
  link_label: string;
  url: string;
  description: string;
  bullets: string[];
};

type SkillGroup = {
  category: string;
  items: string[];
};

type ProfileBuilderFormProps = {
  candidateProfile: Record<string, unknown>;
  preferences: Record<string, unknown>;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function linesToArray(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function delimitedListToArray(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function bulletsToText(bullets: Bullet[] | string[]): string {
  return bullets
    .map((bullet) => (typeof bullet === "string" ? bullet : bullet.text))
    .filter(Boolean)
    .join("\n");
}

function textToBullets(value: string, prefix: string): Bullet[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((text, index) => ({ id: `${prefix}_b${index + 1}`, text }));
}

function normalizeExperience(value: unknown, index: number): Experience {
  const record = asRecord(value);
  const rawBullets = Array.isArray(record.bullets) ? record.bullets : [];
  return {
    id: asString(record.id) || `exp_${index + 1}`,
    company: asString(record.company),
    role: asString(record.role),
    start_date: asString(record.start_date),
    end_date: asString(record.end_date),
    location: asString(record.location),
    bullets: rawBullets.map((bullet, bulletIndex) => {
      if (typeof bullet === "string") {
        return { id: `exp_${index + 1}_b${bulletIndex + 1}`, text: bullet };
      }
      const bulletRecord = asRecord(bullet);
      return {
        id: asString(bulletRecord.id) || `exp_${index + 1}_b${bulletIndex + 1}`,
        text: asString(bulletRecord.text)
      };
    })
  };
}

function normalizeEducation(value: unknown, index: number): Education {
  const record = asRecord(value);
  return {
    id: asString(record.id) || `edu_${index + 1}`,
    school: asString(record.school) || asString(record.education),
    degree: asString(record.degree),
    field: asString(record.field),
    start_date: asString(record.start_date),
    end_date: asString(record.end_date),
    graduation_date: asString(record.graduation_date),
    gpa: asString(record.gpa),
    location: asString(record.location)
  };
}

function normalizeProject(value: unknown, index: number): Project {
  const record = asRecord(value);
  return {
    id: asString(record.id) || `proj_${index + 1}`,
    name: asString(record.name),
    link_label: asString(record.link_label) || "GitHub",
    url: asString(record.url),
    description: asString(record.description),
    bullets: asStringArray(record.bullets)
  };
}

function normalizeSkillGroup(value: unknown): SkillGroup {
  const record = asRecord(value);
  return {
    category: asString(record.category),
    items: asStringArray(record.items)
  };
}

export function ProfileBuilderForm({ candidateProfile, preferences }: ProfileBuilderFormProps) {
  const identity = asRecord(candidateProfile.identity);
  const links = asRecord(candidateProfile.links);
  const salary = asRecord(preferences.salary_expectations);
  const [experiences, setExperiences] = useState<Experience[]>(
    Array.isArray(candidateProfile.experience) && candidateProfile.experience.length
      ? candidateProfile.experience.map(normalizeExperience)
      : [normalizeExperience({}, 0)]
  );
  const [education, setEducation] = useState<Education[]>(
    Array.isArray(candidateProfile.education) && candidateProfile.education.length
      ? candidateProfile.education.map(normalizeEducation)
      : [normalizeEducation({}, 0)]
  );
  const [projects, setProjects] = useState<Project[]>(
    Array.isArray(candidateProfile.academic_projects) && candidateProfile.academic_projects.length
      ? candidateProfile.academic_projects.map(normalizeProject)
      : [normalizeProject({}, 0)]
  );
  const [skillGroups, setSkillGroups] = useState<SkillGroup[]>(
    Array.isArray(candidateProfile.technical_skills) ? candidateProfile.technical_skills.map(normalizeSkillGroup) : []
  );

  function buildCandidateProfile(formData: FormData) {
    const expCount = Number(formData.get("experience_count") || 0);
    const eduCount = Number(formData.get("education_count") || 0);
    const projectCount = Number(formData.get("project_count") || 0);
    const skillGroupCount = Number(formData.get("skill_group_count") || 0);

    return {
      ...candidateProfile,
      identity: {
        full_name: String(formData.get("full_name") || "").trim(),
        email: String(formData.get("email") || "").trim(),
        phone: String(formData.get("phone") || "").trim(),
        location: String(formData.get("location") || "").trim()
      },
      links: {
        linkedin: String(formData.get("linkedin") || "").trim(),
        github: String(formData.get("github") || "").trim(),
        portfolio: String(formData.get("portfolio") || "").trim()
      },
      summary: String(formData.get("summary") || "").trim(),
      skills: delimitedListToArray(String(formData.get("skills") || "")),
      experience: Array.from({ length: expCount }, (_, index) => {
        const id = `exp_${index + 1}`;
        return {
          id,
          company: String(formData.get(`experience_${index}_company`) || "").trim(),
          role: String(formData.get(`experience_${index}_role`) || "").trim(),
          start_date: String(formData.get(`experience_${index}_start_date`) || "").trim(),
          end_date: String(formData.get(`experience_${index}_end_date`) || "").trim(),
          location: String(formData.get(`experience_${index}_location`) || "").trim(),
          bullets: textToBullets(String(formData.get(`experience_${index}_bullets`) || ""), id)
        };
      }).filter((item) => item.company || item.role || item.bullets.length),
      education: Array.from({ length: eduCount }, (_, index) => ({
        id: `edu_${index + 1}`,
        school: String(formData.get(`education_${index}_school`) || "").trim(),
        degree: String(formData.get(`education_${index}_degree`) || "").trim(),
        field: String(formData.get(`education_${index}_field`) || "").trim(),
        start_date: String(formData.get(`education_${index}_start_date`) || "").trim(),
        end_date: String(formData.get(`education_${index}_end_date`) || "").trim(),
        graduation_date: String(formData.get(`education_${index}_graduation_date`) || "").trim(),
        gpa: String(formData.get(`education_${index}_gpa`) || "").trim(),
        location: String(formData.get(`education_${index}_location`) || "").trim()
      })).filter((item) => item.school || item.degree || item.field),
      certifications: delimitedListToArray(String(formData.get("certifications") || "")),
      academic_projects: Array.from({ length: projectCount }, (_, index) => ({
        id: `proj_${index + 1}`,
        name: String(formData.get(`project_${index}_name`) || "").trim(),
        link_label: String(formData.get(`project_${index}_link_label`) || "").trim() || "GitHub",
        url: String(formData.get(`project_${index}_url`) || "").trim(),
        description: String(formData.get(`project_${index}_description`) || "").trim(),
          bullets: linesToArray(String(formData.get(`project_${index}_bullets`) || ""))
      })).filter((item) => item.name || item.description || item.bullets.length),
      technical_skills: Array.from({ length: skillGroupCount }, (_, index) => ({
        category: String(formData.get(`skill_group_${index}_category`) || "").trim(),
        items: delimitedListToArray(String(formData.get(`skill_group_${index}_items`) || ""))
      })).filter((item) => item.category || item.items.length)
    };
  }

  function buildPreferences(formData: FormData) {
    return {
      work_authorization: String(formData.get("work_authorization") || "").trim(),
      sponsorship_required: String(formData.get("sponsorship_required") || "unknown").trim(),
      preferred_locations: linesToArray(String(formData.get("preferred_locations") || "")),
      salary_expectations: {
        currency: String(formData.get("salary_currency") || "USD").trim(),
        min: formData.get("salary_min") ? Number(formData.get("salary_min")) : null,
        max: formData.get("salary_max") ? Number(formData.get("salary_max")) : null
      }
    };
  }

  function preparePayload(event: FormEvent<HTMLFormElement>) {
    const form = event.currentTarget;
    const formData = new FormData(form);
    const candidateInput = form.querySelector<HTMLInputElement>('input[name="candidate_profile"]');
    const preferencesInput = form.querySelector<HTMLInputElement>('input[name="preferences"]');
    if (candidateInput) {
      candidateInput.value = JSON.stringify(buildCandidateProfile(formData));
    }
    if (preferencesInput) {
      preferencesInput.value = JSON.stringify(buildPreferences(formData));
    }
  }

  return (
    <form className="panel profile-builder-form" method="post" action="/api/profile" onSubmit={preparePayload}>
      <input type="hidden" name="candidate_profile" />
      <input type="hidden" name="preferences" />
      <input type="hidden" name="experience_count" value={experiences.length} />
      <input type="hidden" name="education_count" value={education.length} />
      <input type="hidden" name="project_count" value={projects.length} />
      <input type="hidden" name="skill_group_count" value={skillGroups.length} />

      <section className="profile-builder-hero">
        <p className="eyebrow">Profile builder</p>
        <h2>Give the copilot your factual resume inventory.</h2>
        <p>
          Add all relevant experience, projects, skills, and bullets here. JobApply Copilot compares this inventory with each job description,
          selects the most relevant bullets/projects, and tailors the resume without inventing unsupported claims.
        </p>
      </section>

      <section className="form-section">
        <h3>Basic details</h3>
        <div className="form-grid two">
          <label>Full name<input name="full_name" defaultValue={asString(identity.full_name)} /></label>
          <label>Email<input name="email" defaultValue={asString(identity.email)} /></label>
          <label>Phone<input name="phone" defaultValue={asString(identity.phone)} /></label>
          <label>Location<input name="location" defaultValue={asString(identity.location)} placeholder="City, State or remote preference" /></label>
          <label>LinkedIn<input name="linkedin" defaultValue={asString(links.linkedin)} /></label>
          <label>GitHub<input name="github" defaultValue={asString(links.github)} /></label>
          <label className="wide">Portfolio<input name="portfolio" defaultValue={asString(links.portfolio)} /></label>
        </div>
        <label>
          Professional summary
          <textarea name="summary" rows={4} defaultValue={asString(candidateProfile.summary)} placeholder="Short factual summary. Example: Machine Learning and Data Science graduate with..." />
        </label>
      </section>

      <section className="form-section">
        <h3>Skills and preferences</h3>
        <div className="form-grid two">
          <label>
            Core skills
            <textarea name="skills" rows={7} defaultValue={asStringArray(candidateProfile.skills).join("\n")} placeholder="Python&#10;SQL&#10;Machine Learning" />
          </label>
          <label>
            Preferred locations
            <textarea name="preferred_locations" rows={7} defaultValue={asStringArray(preferences.preferred_locations).join("\n")} placeholder="San Francisco Bay Area&#10;Remote&#10;Open to relocation where appropriate" />
          </label>
          <label>Work authorization<input name="work_authorization" defaultValue={asString(preferences.work_authorization)} placeholder="Authorized to work in the United States" /></label>
          <label>
            Sponsorship required
            <select name="sponsorship_required" defaultValue={asString(preferences.sponsorship_required) || "unknown"}>
              <option value="unknown">Prefer not to say / confirm manually</option>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </select>
          </label>
          <label>Salary currency<input name="salary_currency" defaultValue={asString(salary.currency) || "USD"} /></label>
          <label>Minimum salary<input name="salary_min" type="number" defaultValue={asString(salary.min)} /></label>
          <label>Maximum salary<input name="salary_max" type="number" defaultValue={asString(salary.max)} /></label>
        </div>
      </section>

      <section className="form-section">
        <h3>Experience</h3>
        <p className="small-note">Add every role you want the copilot to choose from. Put one accomplishment bullet per line.</p>
        {experiences.map((item, index) => (
          <div className="repeat-card" key={item.id || index}>
            <h4>Experience {index + 1}</h4>
            <div className="form-grid two">
              <label>Company<input name={`experience_${index}_company`} defaultValue={item.company} /></label>
              <label>Role<input name={`experience_${index}_role`} defaultValue={item.role} /></label>
              <label>Start date<input name={`experience_${index}_start_date`} defaultValue={item.start_date} placeholder="2023-02" /></label>
              <label>End date<input name={`experience_${index}_end_date`} defaultValue={item.end_date} placeholder="2024-09 or Present" /></label>
              <label className="wide">Location<input name={`experience_${index}_location`} defaultValue={item.location} /></label>
              <label className="wide">
                Bullets
                <textarea name={`experience_${index}_bullets`} rows={5} defaultValue={bulletsToText(item.bullets)} placeholder="Automated data pipelines using Python...&#10;Built dashboards that improved..." />
              </label>
            </div>
          </div>
        ))}
        <button className="secondary-button" type="button" onClick={() => setExperiences((items) => [...items, normalizeExperience({}, items.length)])}>
          Add another experience
        </button>
      </section>

      <section className="form-section">
        <h3>Education and certifications</h3>
        {education.map((item, index) => (
          <div className="repeat-card" key={item.id || index}>
            <h4>Education {index + 1}</h4>
            <div className="form-grid two">
              <label>School<input name={`education_${index}_school`} defaultValue={item.school} /></label>
              <label>Degree<input name={`education_${index}_degree`} defaultValue={item.degree} /></label>
              <label>Field<input name={`education_${index}_field`} defaultValue={item.field} /></label>
              <label>GPA<input name={`education_${index}_gpa`} defaultValue={item.gpa} /></label>
              <label>Start date<input name={`education_${index}_start_date`} defaultValue={item.start_date} /></label>
              <label>End date<input name={`education_${index}_end_date`} defaultValue={item.end_date} /></label>
              <label>Graduation date<input name={`education_${index}_graduation_date`} defaultValue={item.graduation_date} /></label>
              <label>Location<input name={`education_${index}_location`} defaultValue={item.location} /></label>
            </div>
          </div>
        ))}
        <button className="secondary-button" type="button" onClick={() => setEducation((items) => [...items, normalizeEducation({}, items.length)])}>
          Add another education
        </button>
        <label>
          Certifications
          <textarea name="certifications" rows={5} defaultValue={asStringArray(candidateProfile.certifications).join("\n")} placeholder="AWS Certified AI Practitioner&#10;IBM Data Science Professional Certificate" />
        </label>
      </section>

      <section className="form-section">
        <h3>Projects</h3>
        <p className="small-note">Add all portfolio projects. For each job, the copilot will pick the strongest matching projects instead of listing everything.</p>
        {projects.map((item, index) => (
          <div className="repeat-card" key={item.id || index}>
            <h4>Project {index + 1}</h4>
            <div className="form-grid two">
              <label>Name<input name={`project_${index}_name`} defaultValue={item.name} /></label>
              <label>Link label<input name={`project_${index}_link_label`} defaultValue={item.link_label} /></label>
              <label className="wide">URL<input name={`project_${index}_url`} defaultValue={item.url} /></label>
              <label className="wide">Description<textarea name={`project_${index}_description`} rows={3} defaultValue={item.description} /></label>
              <label className="wide">Project bullets<textarea name={`project_${index}_bullets`} rows={4} defaultValue={item.bullets.join("\n")} /></label>
            </div>
          </div>
        ))}
        <button className="secondary-button" type="button" onClick={() => setProjects((items) => [...items, normalizeProject({}, items.length)])}>
          Add another project
        </button>
      </section>

      <section className="form-section">
        <h3>Technical skill groups</h3>
        {skillGroups.map((item, index) => (
          <div className="repeat-card compact" key={`${item.category}-${index}`}>
            <div className="form-grid two">
              <label>Category<input name={`skill_group_${index}_category`} defaultValue={item.category} placeholder="Programming Languages" /></label>
              <label>Items<textarea name={`skill_group_${index}_items`} rows={4} defaultValue={item.items.join("\n")} placeholder="Python&#10;SQL&#10;R" /></label>
            </div>
          </div>
        ))}
        {!skillGroups.length ? <p className="small-note">Add technical skill groups later if needed. Core skills above are enough to start.</p> : null}
        <button className="secondary-button" type="button" onClick={() => setSkillGroups((items) => [...items, { category: "", items: [] }])}>
          Add skill group
        </button>
      </section>

      <button className="primary-button profile-save-button" type="submit">Save profile for tailoring</button>
    </form>
  );
}
