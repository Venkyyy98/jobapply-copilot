"use client";

import { useState } from "react";
import type { CSSProperties } from "react";

import type { ApplicationActivity } from "@/lib/types";

const periodLabels = {
  today: "Today",
  week: "This week",
  month: "This month",
  all: "All time"
} as const;

function formatDay(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC"
  }).format(new Date(`${value}T00:00:00Z`));
}

export function ApplicationActivitySummary({
  activity,
  filtered
}: {
  activity: ApplicationActivity;
  filtered: boolean;
}) {
  return (
    <>
      <section className="activity-summary-grid" aria-label="Application activity totals">
        {(Object.keys(periodLabels) as Array<keyof typeof periodLabels>).map((period) => (
          <article className="activity-summary-card" key={period}>
            <p>{periodLabels[period]}</p>
            <div>
              <span><strong>{activity.periods[period].checked}</strong> checked</span>
              <span><strong>{activity.periods[period].applied}</strong> applied</span>
            </div>
          </article>
        ))}
      </section>
      {filtered ? (
        <div className="filtered-counts">
          Current filter: <strong>{activity.filtered.checked}</strong> checked and{" "}
          <strong>{activity.filtered.applied}</strong> applied
        </div>
      ) : null}
    </>
  );
}

export function ApplicationActivityCharts({ activity }: { activity: ApplicationActivity }) {
  const periods = {
    today: "Daily",
    week: "Weekly",
    month: "Monthly"
  } as const;
  const [period, setPeriod] = useState<keyof typeof periods>("today");
  const checked = activity.periods[period].checked;
  const applied = activity.periods[period].applied;
  const checkedOnly = Math.max(checked - applied, 0);
  const total = applied + checkedOnly;
  const appliedAngle = total ? (applied / total) * 360 : 0;
  const style = { "--applied-angle": `${appliedAngle}deg` } as CSSProperties;

  return (
    <section className="application-chart-section">
      <div className="section-head compact">
        <div>
          <h2>Application progress</h2>
          <p className="muted">Choose a period to compare applications submitted with jobs checked but not yet marked applied.</p>
        </div>
      </div>
      <div className="chart-period-selector" role="group" aria-label="Chart period">
        {(Object.keys(periods) as Array<keyof typeof periods>).map((option) => (
          <button
            type="button"
            key={option}
            className={period === option ? "active" : ""}
            aria-pressed={period === option}
            onClick={() => setPeriod(option)}
          >
            {periods[option]}
          </button>
        ))}
      </div>
      <article className="application-chart-card">
        <div
          className="donut-chart"
          style={style}
          aria-label={`${periods[period]}: ${applied} applied, ${checkedOnly} checked only`}
        >
          <div className="donut-center">
            <strong>{applied}</strong>
            <span>applied</span>
          </div>
        </div>
        <div>
          <h3>{periods[period]}</h3>
          <p><span className="chart-key applied-key" /> {applied} applied</p>
          <p><span className="chart-key checked-key" /> {checkedOnly} checked only</p>
          <p className="muted">{checked} jobs checked in this period</p>
        </div>
      </article>
    </section>
  );
}

export function DailyApplicationActivity({ activity }: { activity: ApplicationActivity }) {
  return (
    <section className="panel daily-activity-panel">
      <div className="section-head compact">
        <div>
          <h2>Daily activity</h2>
          <p className="muted">Your latest 31 active days, based on the first time each job was checked or marked applied.</p>
        </div>
      </div>
      <div className="activity-table-wrap">
        <table className="activity-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Checked</th>
              <th>Applied</th>
            </tr>
          </thead>
          <tbody>
            {activity.daily.map((day) => (
              <tr key={day.date}>
                <td>{formatDay(day.date)}</td>
                <td>{day.checked}</td>
                <td>{day.applied}</td>
              </tr>
            ))}
            {!activity.daily.length ? (
              <tr>
                <td colSpan={3} className="empty-state">No checked or applied activity yet.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
