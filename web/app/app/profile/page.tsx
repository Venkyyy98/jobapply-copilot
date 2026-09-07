import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { ExtensionTokenPanel } from "@/components/extension-token-panel";
import { ProfileBuilderForm } from "@/components/profile-builder-form";
import { authOptions } from "@/lib/auth";
import { fetchMyProfile } from "@/lib/api";

const starterCandidateProfile = {
  identity: {
    full_name: "",
    email: "",
    phone: "",
    location: ""
  },
  links: {
    linkedin: "",
    github: "",
    portfolio: ""
  },
  summary: "",
  skills: [],
  experience: [],
  education: [],
  academic_projects: [],
  technical_skills: []
};

const starterPreferences = {
  work_authorization: "",
  sponsorship_required: "unknown",
  preferred_locations: [],
  salary_expectations: {
    currency: "USD",
    min: null,
    max: null
  }
};

export default async function ProfilePage({ searchParams }: { searchParams: Promise<{ saved?: string; error?: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    redirect("/signin");
  }

  const params = await searchParams;
  const profile = await fetchMyProfile().catch(() => ({
    candidate_profile: starterCandidateProfile,
    preferences: starterPreferences,
    profile_complete: false,
    compliance_notes: ["Profile service is unavailable."],
    updated_at: ""
  }));
  const candidateProfile = Object.keys(profile.candidate_profile || {}).length ? profile.candidate_profile : starterCandidateProfile;
  const preferences = Object.keys(profile.preferences || {}).length ? profile.preferences : starterPreferences;

  return (
    <>
      <div className="section-head">
        <div>
          <h1>Beta onboarding</h1>
          <p className="muted">Store factual resume/profile data for document generation and connect the hosted extension.</p>
        </div>
        {params.saved ? <span className="pill">Saved</span> : null}
      </div>
      {params.error ? <div className="auth-warning">{params.error}</div> : null}

      <section className="profile-grid">
        <ProfileBuilderForm candidateProfile={candidateProfile} preferences={preferences} />

        <div className="stack">
          <section className="panel">
            <h2>Profile status</h2>
            <p className={profile.profile_complete ? "inline-status" : "warning"}>
              {profile.profile_complete ? "Ready for compliant document generation." : "Needs required profile facts."}
            </p>
            <ul className="list-card">
              {profile.compliance_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
              {!profile.compliance_notes.length ? <li>No blocking profile issues found.</li> : null}
            </ul>
          </section>
          <ExtensionTokenPanel
            disabled={!profile.profile_complete}
            disabledReason="Complete and save the required profile facts before creating an extension token."
          />
        </div>
      </section>
    </>
  );
}
