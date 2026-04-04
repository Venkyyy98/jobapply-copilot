type Props = {
  searchParams: Record<string, string | undefined>;
  roleFamilies: string[];
};

export function JobsFilterBar({ searchParams, roleFamilies }: Props) {
  return (
    <form className="filters-panel" action="/jobs">
      <div className="filters-grid">
        <label>
          Search
          <input type="text" name="q" defaultValue={searchParams.q || ""} placeholder="Title, company, keyword" />
        </label>
        <label>
          Role family
          <select name="role_family" defaultValue={searchParams.role_family || ""}>
            <option value="">All roles</option>
            {roleFamilies.map((family) => (
              <option key={family} value={family}>
                {family}
              </option>
            ))}
          </select>
        </label>
        <label>
          Location
          <input type="text" name="location" defaultValue={searchParams.location || ""} placeholder="New York, Remote" />
        </label>
        <label>
          Min fit
          <input type="number" min="0" max="100" name="fit_min" defaultValue={searchParams.fit_min || ""} />
        </label>
        <label>
          Sort
          <select name="sort" defaultValue={searchParams.sort || "newest"}>
            <option value="newest">Newest</option>
            <option value="fit">Best fit</option>
            <option value="most_applied">Most applied</option>
            <option value="most_saved">Most saved</option>
          </select>
        </label>
      </div>
      <button type="submit" className="primary-button">
        Apply filters
      </button>
    </form>
  );
}
