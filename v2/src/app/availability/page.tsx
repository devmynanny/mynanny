"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { CalendarEvent, MonthCalendar } from "@/components/month-calendar";
import { apiJson } from "@/lib/api";
import { CalendarCheck, LoaderCircle, Repeat2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

type Availability = {
  id: number;
  date?: string | null;
  start_dt: string;
  end_dt: string;
  type: "available" | "blocked";
};

function availabilityDate(row: Availability) {
  return row.date || row.start_dt.slice(0, 10);
}

export default function AvailabilityPage() {
  const [rows, setRows] = useState<Availability[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("17:00");
  const [status, setStatus] = useState("");
  const [weeklyStart, setWeeklyStart] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [weeks, setWeeks] = useState("4");
  const [weekdays, setWeekdays] = useState<number[]>([0, 1, 2, 3, 4]);
  const [weeklyType, setWeeklyType] = useState<"available" | "blocked">(
    "available",
  );
  async function load() {
    const data = await apiJson<{ results: Availability[] }>(
      "/nannies/me/availability",
    );
    setRows(data.results || []);
  }
  useEffect(() => {
    apiJson<{ results: Availability[] }>("/nannies/me/availability")
      .then((data) => setRows(data.results || []))
      .catch((err) =>
        setStatus(
          err instanceof Error ? err.message : "Unable to load availability.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  async function selectDate(date: string) {
    const protectedDay = rows.some(
      (row) => availabilityDate(row) === date && row.type === "blocked",
    );
    if (protectedDay) {
      setStatus("This day is protected by your permanent work schedule.");
      return;
    }
    const existing = rows.find(
      (row) => availabilityDate(row) === date && row.type === "available",
    );
    setSaving(true);
    setStatus("");
    try {
      if (existing) {
        await apiJson(`/nannies/me/availability/${existing.id}`, {
          method: "DELETE",
        });
        setRows((current) => current.filter((row) => row.id !== existing.id));
        setStatus("Availability removed.");
      } else {
        const created = await apiJson<{ id: number }>(
          "/nannies/me/availability",
          {
            method: "POST",
            body: JSON.stringify({
              start_dt: `${date}T${startTime}:00`,
              end_dt: `${date}T${endTime}:00`,
              type: "available",
            }),
          },
        );
        setRows((current) => [
          ...current,
          {
            id: created.id,
            date,
            start_dt: `${date}T${startTime}:00`,
            end_dt: `${date}T${endTime}:00`,
            type: "available",
          },
        ]);
        setStatus("Availability saved.");
      }
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : "Unable to update availability.",
      );
    } finally {
      setSaving(false);
    }
  }
  async function clearAll() {
    if (!window.confirm("Clear all availability from your calendar?")) return;
    setSaving(true);
    try {
      await apiJson("/nannies/me/availability", { method: "DELETE" });
      await load();
      setStatus(
        "Your own availability was cleared. Permanent work schedule blocks remain protected.",
      );
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : "Unable to clear calendar.",
      );
    } finally {
      setSaving(false);
    }
  }
  function toggleWeekday(day: number) {
    setWeekdays((current) =>
      current.includes(day)
        ? current.filter((value) => value !== day)
        : [...current, day].sort(),
    );
  }
  async function applyWeekly() {
    if (!weekdays.length) {
      setStatus("Select at least one weekday.");
      return;
    }
    setSaving(true);
    setStatus("");
    try {
      const result = await apiJson<{ created: number; skipped: number }>(
        "/nannies/me/availability/weekly",
        {
          method: "POST",
          body: JSON.stringify({
            start_date: weeklyStart,
            weeks: Number(weeks),
            weekdays,
            start_time: startTime,
            end_time: endTime,
            type: weeklyType,
          }),
        },
      );
      await load();
      setStatus(
        `${result.created} dates added${result.skipped ? `; ${result.skipped} already existed` : ""}.`,
      );
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : "Unable to apply weekly pattern.",
      );
    } finally {
      setSaving(false);
    }
  }
  const eventsByDate = new Map<string, CalendarEvent>();
  rows.forEach((row) => {
    const date = availabilityDate(row);
    const current = eventsByDate.get(date);
    if (!current || row.type === "blocked") {
      eventsByDate.set(date, {
        date,
        label: row.type === "available" ? "Available" : "Unavailable",
        tone: row.type === "available" ? "green" : "coral",
      });
    }
  });
  const events = Array.from(eventsByDate.values());
  return (
    <AuthenticatedPage>
      {(role) =>
        role !== "nanny" ? (
          <div className="card mx-auto max-w-xl p-8 text-center">
            <h1 className="text-2xl font-bold">Nanny access only</h1>
          </div>
        ) : (
          <div className="mx-auto max-w-6xl">
            <div className="eyebrow">Nanny schedule</div>
            <h1 className="display mt-2 text-4xl sm:text-5xl">
              Set your availability.
            </h1>
            <p className="mt-3 text-[var(--muted)]">
              Tap a date to add or remove it. Existing bookings always stay
              protected.
            </p>
            <div className="mt-7 grid gap-6 xl:grid-cols-[1.25fr_.75fr]">
              <div className="card p-4 sm:p-6">
                {loading ? (
                  <div className="flex min-h-96 items-center justify-center">
                    <LoaderCircle className="animate-spin" />
                  </div>
                ) : (
                  <MonthCalendar
                    selectable
                    events={events}
                    onSelect={selectDate}
                  />
                )}
              </div>
              <aside className="grid content-start gap-5">
                <div className="card p-6">
                  <CalendarCheck className="text-[var(--green)]" />
                  <h2 className="mt-4 text-xl font-bold">Working hours</h2>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    These times apply when you add a date.
                  </p>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <label className="text-xs font-bold">
                      Start
                      <input
                        type="time"
                        className="field mt-2"
                        value={startTime}
                        onChange={(e) => setStartTime(e.target.value)}
                      />
                    </label>
                    <label className="text-xs font-bold">
                      Finish
                      <input
                        type="time"
                        className="field mt-2"
                        value={endTime}
                        onChange={(e) => setEndTime(e.target.value)}
                      />
                    </label>
                  </div>
                  {status && (
                    <div
                      role="status"
                      className="mt-4 rounded-xl bg-[var(--blue-pale)] p-3 text-sm"
                    >
                      {status}
                    </div>
                  )}
                  <div className="mt-5 flex gap-3">
                    <button
                      className="btn-secondary flex-1"
                      disabled={saving}
                      onClick={clearAll}
                    >
                      <Trash2 size={16} />
                      Clear
                    </button>
                  </div>
                </div>
                <div className="card p-6">
                  <Repeat2 className="text-[var(--blue-dark)]" />
                  <h2 className="mt-4 text-lg font-bold">Weekly pattern</h2>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    Choose your usual days and apply them for several weeks.
                  </p>
                  <div className="mt-5 grid gap-4">
                    <label className="text-xs font-bold">
                      Starting from
                      <input
                        type="date"
                        className="field mt-2"
                        value={weeklyStart}
                        onChange={(e) => setWeeklyStart(e.target.value)}
                      />
                    </label>
                    <label className="text-xs font-bold">
                      Repeat for
                      <select
                        className="field mt-2"
                        value={weeks}
                        onChange={(e) => setWeeks(e.target.value)}
                      >
                        {[2, 4, 6, 8, 12, 26, 52].map((value) => (
                          <option key={value} value={value}>
                            {value} weeks
                          </option>
                        ))}
                      </select>
                    </label>
                    <div>
                      <div className="mb-2 text-xs font-bold">Weekdays</div>
                      <div className="grid grid-cols-4 gap-2">
                        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                          (label, index) => (
                            <button
                              type="button"
                              key={label}
                              onClick={() => toggleWeekday(index)}
                              className={`min-h-10 rounded-xl border text-xs font-bold ${weekdays.includes(index) ? "border-[var(--blue-dark)] bg-[var(--blue-dark)] text-white" : "border-[var(--line)] bg-white"}`}
                            >
                              {label}
                            </button>
                          ),
                        )}
                      </div>
                    </div>
                    <label className="text-xs font-bold">
                      Pattern type
                      <select
                        className="field mt-2"
                        value={weeklyType}
                        onChange={(e) =>
                          setWeeklyType(
                            e.target.value as "available" | "blocked",
                          )
                        }
                      >
                        <option value="available">Available</option>
                        <option value="blocked">Unavailable / blocked</option>
                      </select>
                    </label>
                    <button
                      className="btn-primary w-full"
                      disabled={saving}
                      onClick={applyWeekly}
                    >
                      {saving ? (
                        <LoaderCircle className="animate-spin" size={17} />
                      ) : (
                        <Repeat2 size={17} />
                      )}
                      Apply weekly pattern
                    </button>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        )
      }
    </AuthenticatedPage>
  );
}
