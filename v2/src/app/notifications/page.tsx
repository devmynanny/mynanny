"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { Bell, CheckCheck, LoaderCircle } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useState } from "react";

type Notice = {
  id: number;
  title: string;
  body: string;
  action_url?: string | null;
  read: boolean;
  created_at: string;
};

export default function NotificationsPage() {
  return <AuthenticatedPage>{() => <Notifications />}</AuthenticatedPage>;
}

function Notifications() {
  const [rows, setRows] = useState<Notice[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  async function load() {
    try {
      const data = await apiJson<{ unread_count: number; results: Notice[] }>(
        "/notifications",
      );
      setRows(data.results || []);
      setUnread(data.unread_count || 0);
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Unable to load notifications.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    Promise.resolve().then(() => load());
  }, []);
  async function markRead(row: Notice) {
    if (!row.read) {
      await apiJson(`/notifications/${row.id}/read`, { method: "PATCH" });
      setRows((current) =>
        current.map((item) =>
          item.id === row.id ? { ...item, read: true } : item,
        ),
      );
      setUnread((current) => Math.max(0, current - 1));
    }
  }
  async function markAll() {
    await apiJson("/notifications/read-all", { method: "POST" });
    setRows((current) => current.map((row) => ({ ...row, read: true })));
    setUnread(0);
  }
  return (
    <div className="mx-auto max-w-4xl">
      <div className="eyebrow">Updates & actions</div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-4xl sm:text-5xl">Notifications.</h1>
          <p className="mt-3 text-[var(--muted)]">
            Important booking, payment, screening and account updates in one
            place.
          </p>
        </div>
        {unread > 0 && (
          <button className="btn-secondary" onClick={() => void markAll()}>
            <CheckCheck size={17} />
            Mark all read
          </button>
        )}
      </div>
      {message && (
        <div className="mt-5 rounded-2xl bg-red-50 p-4 text-red-800">
          {message}
        </div>
      )}
      <section className="card mt-7 overflow-hidden">
        {loading ? (
          <div className="flex min-h-64 items-center justify-center">
            <LoaderCircle className="animate-spin" />
          </div>
        ) : rows.length ? (
          <div className="divide-y divide-[var(--line)]">
            {rows.map((row) => {
              const content = (
                <div
                  className={`flex gap-4 p-6 transition hover:bg-slate-50 ${row.read ? "opacity-65" : "bg-[var(--blue-pale)]/45"}`}
                >
                  <span
                    className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${row.read ? "bg-slate-100 text-slate-500" : "bg-white text-[var(--blue-dark)] shadow-sm"}`}
                  >
                    <Bell size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="font-extrabold">{row.title}</h2>
                      {!row.read && (
                        <span className="pill !border-transparent !bg-[var(--coral)] !text-white">
                          New
                        </span>
                      )}
                    </div>
                    <p className="mt-2 leading-6 text-[var(--muted)]">
                      {row.body}
                    </p>
                    <p className="mt-3 text-xs font-semibold text-[var(--muted)]">
                      {new Date(row.created_at).toLocaleString("en-ZA")}
                    </p>
                  </div>
                </div>
              );
              return row.action_url ? (
                <Link
                  href={row.action_url as Route}
                  key={row.id}
                  onClick={() => void markRead(row)}
                >
                  {content}
                </Link>
              ) : (
                <button
                  className="block w-full text-left"
                  key={row.id}
                  onClick={() => void markRead(row)}
                >
                  {content}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="p-12 text-center">
            <Bell className="mx-auto text-[var(--blue-dark)]" size={34} />
            <h2 className="mt-4 text-xl font-bold">You are all caught up</h2>
            <p className="mt-2 text-[var(--muted)]">
              New updates will appear here.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
