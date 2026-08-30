import { ReactNode } from "react";

export function PlacementHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <div className="max-w-4xl">
      <div className="eyebrow">{eyebrow}</div>
      <h1 className="display mt-2 text-4xl sm:text-6xl">{title}</h1>
      <p className="mt-4 max-w-3xl text-base leading-7 text-[var(--muted)] sm:text-lg">
        {body}
      </p>
    </div>
  );
}

export function PlacementNotice({ message }: { message: string }) {
  return message ? (
    <div
      role="status"
      className="mt-5 rounded-2xl bg-[var(--blue-pale)] px-5 py-4 text-sm font-semibold"
    >
      {message}
    </div>
  ) : null;
}

export function PlacementInfo({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-extrabold uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
      <div className="mt-2 whitespace-pre-line text-sm leading-6">{value}</div>
    </div>
  );
}

export function PlacementField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label>
      <span className="mb-2 block text-sm font-bold">{label}</span>
      {children}
    </label>
  );
}
