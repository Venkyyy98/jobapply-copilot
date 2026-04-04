export function StatsGrid({ counts }: { counts: Record<string, number> }) {
  const items = [
    ["Saved", counts.saved || 0],
    ["Analyzed", counts.analyzed || 0],
    ["Generated docs", counts.generated_docs || 0],
    ["Applied", counts.applied || 0],
    ["Outreach", counts.outreach_started || 0]
  ];
  return (
    <div className="stats-grid">
      {items.map(([label, value]) => (
        <div key={label} className="stat-card">
          <p>{label}</p>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}
