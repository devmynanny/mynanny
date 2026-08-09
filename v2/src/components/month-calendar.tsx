"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

export type CalendarEvent = {
  date: string;
  label: string;
  tone?: "blue" | "green" | "coral";
};

function isoDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function MonthCalendar({
  events = [],
  selectable = false,
  selectedDates,
  onSelect,
}: {
  events?: CalendarEvent[];
  selectable?: boolean;
  selectedDates?: string[];
  onSelect?: (date: string) => void;
}) {
  const [cursor, setCursor] = useState(() => new Date());
  const [selected, setSelected] = useState<string[]>([]);
  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const offset = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const cells = Array.from({ length: 42 }, (_, i) => i - offset + 1);
  const eventMap = new Map(events.map((event) => [event.date, event]));
  const today = isoDate(new Date());

  function choose(date: string) {
    if (!selectable && !onSelect) return;
    if (selectable && selectedDates === undefined)
      setSelected((current) =>
        current.includes(date)
          ? current.filter((item) => item !== date)
          : [...current, date],
      );
    onSelect?.(date);
  }

  return (
    <div className="rounded-[20px] border border-[var(--line)] bg-white p-3 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <button
          className="btn-quiet !min-h-10 !px-3"
          aria-label="Previous month"
          onClick={() => setCursor(new Date(year, month - 1, 1))}
        >
          <ChevronLeft size={18} />
        </button>
        <h3 className="text-base font-bold">
          {cursor.toLocaleDateString("en-ZA", {
            month: "long",
            year: "numeric",
          })}
        </h3>
        <button
          className="btn-quiet !min-h-10 !px-3"
          aria-label="Next month"
          onClick={() => setCursor(new Date(year, month + 1, 1))}
        >
          <ChevronRight size={18} />
        </button>
      </div>
      <div className="grid grid-cols-7 text-center text-[11px] font-extrabold uppercase tracking-wider text-[var(--muted)]">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
          <div key={day} className="pb-2">
            {day.slice(0, 1)}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, index) => {
          const valid = day > 0 && day <= days;
          const date = valid ? isoDate(new Date(year, month, day)) : "";
          const event = eventMap.get(date);
          const active = (selectedDates ?? selected).includes(date);
          const isToday = date === today;
          return (
            <button
              key={index}
              disabled={!valid}
              onClick={() => choose(date)}
              aria-label={
                valid
                  ? `${date}${isToday ? ", Today" : ""}${event ? `, ${event.label}` : ""}`
                  : undefined
              }
              className={`relative min-h-12 rounded-xl p-1 text-sm transition sm:min-h-16 ${!valid ? "opacity-0" : onSelect ? "cursor-pointer hover:bg-[var(--blue-pale)] focus-visible:ring-2 focus-visible:ring-[var(--blue)]" : ""} ${active ? "bg-[var(--blue-dark)] !text-white" : ""}`}
            >
              {valid && (
                <>
                  <span
                    className={`mx-auto flex h-8 w-8 items-center justify-center rounded-full ${isToday ? (active ? "border-2 border-white font-extrabold" : "border-2 border-[var(--blue-dark)] bg-[var(--blue-pale)] font-extrabold text-[var(--blue-dark)]") : ""}`}
                  >
                    {day}
                  </span>
                  {event && (
                    <span
                      className={`absolute bottom-1.5 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full ${event.tone === "coral" ? "bg-[var(--coral)]" : event.tone === "green" ? "bg-[var(--green)]" : "bg-[var(--blue)]"}`}
                      title={event.label}
                    />
                  )}
                </>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
