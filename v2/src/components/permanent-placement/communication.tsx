"use client";

import { apiJson } from "@/lib/api";
import { Check, LoaderCircle, LockKeyhole, MessageCircle, Phone } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { PermanentCommunication, dateTime } from "./types";

export function InterviewCommunication({ candidateId }: { candidateId: number }) {
  const [data, setData] = useState<PermanentCommunication | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setData(await apiJson<PermanentCommunication>(`/permanent-placements/candidates/${candidateId}/communication`));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load interview communication.");
    }
  }

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const next = await apiJson<PermanentCommunication>(`/permanent-placements/candidates/${candidateId}/communication`);
        if (active) setData(next);
      } catch (nextError) {
        if (active) setError(nextError instanceof Error ? nextError.message : "Unable to load interview communication.");
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [candidateId]);

  async function acceptTerms() {
    setBusy("terms");
    setError("");
    try {
      setData(await apiJson<PermanentCommunication>(`/permanent-placements/candidates/${candidateId}/contact-terms`, {
        method: "POST",
        body: JSON.stringify({ accepted: true }),
      }));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to accept the communication terms.");
    } finally {
      setBusy("");
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!body.trim()) return;
    setBusy("message");
    setError("");
    try {
      setData(await apiJson<PermanentCommunication>(`/permanent-placements/candidates/${candidateId}/messages`, {
        method: "POST",
        body: JSON.stringify({ body }),
      }));
      setBody("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to send the message.");
      await load();
    } finally {
      setBusy("");
    }
  }

  if (!data) return <div className="mt-5 flex items-center gap-2 rounded-2xl border border-[var(--line)] p-4 text-sm text-[var(--muted)]"><LoaderCircle className="animate-spin" size={16} />Loading interview communication…</div>;

  return (
    <section className="mt-5 rounded-2xl border border-[var(--line)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-bold"><MessageCircle size={18} />Interview communication</span>
        <span className="pill">{data.window_open ? "Temporary access" : "Locked"}</span>
      </div>
      {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>}
      {!data.window_open ? (
        <div className="mt-4 flex gap-3 rounded-xl bg-[var(--blue-pale)] p-4 text-sm leading-6"><LockKeyhole className="mt-1 shrink-0" size={17} /><span>{data.locked_reason}</span></div>
      ) : !data.viewer_terms_accepted ? (
        <div className="mt-4 rounded-xl bg-[var(--blue-pale)] p-4 text-sm leading-6">
          <p>{data.terms_text}</p>
          <button className="btn-primary mt-4" disabled={busy === "terms"} onClick={() => void acceptTerms()}>{busy === "terms" ? <LoaderCircle className="animate-spin" size={17} /> : <Check size={17} />}I understand and accept</button>
        </div>
      ) : !data.can_message ? (
        <p className="mt-4 rounded-xl bg-[var(--blue-pale)] p-4 text-sm leading-6">You accepted the temporary contact rules. Waiting for the other party to accept before details and chat are unlocked.</p>
      ) : null}
      {data.contact && (
        <div className="mt-4 rounded-xl bg-[var(--blue-pale)] p-4 text-sm leading-6">
          <div className="flex items-center gap-2 font-bold"><Phone size={16} />Temporary interview contact</div>
          <div className="mt-2">{data.contact.name}</div>
          {data.contact.phone && <div>{data.contact.phone}</div>}
          {data.contact.email && <div>{data.contact.email}</div>}
          <p className="mt-2 text-xs text-[var(--muted)]">This disappears when the nanny checks in or completes the interview. Home addresses are never shown.</p>
        </div>
      )}
      {data.messages.length > 0 && (
        <div className="mt-4 grid max-h-72 gap-2 overflow-y-auto rounded-xl bg-slate-50 p-3">
          {data.messages.map((message) => {
            const own = message.sender_role === data.viewer_role;
            return <div key={message.id} className={`max-w-[88%] rounded-xl px-3 py-2 text-sm ${own ? "ml-auto bg-[var(--blue-dark)] text-white" : "bg-white"}`}><div>{message.body}</div><div className={`mt-1 text-[10px] ${own ? "text-white/70" : "text-[var(--muted)]"}`}>{message.sender_name} · {dateTime(message.created_at)}</div></div>;
          })}
        </div>
      )}
      {data.can_message && (
        <form className="mt-4 flex gap-2" onSubmit={send}>
          <input className="field" maxLength={2000} value={body} onChange={(event) => setBody(event.target.value)} placeholder="Interview logistics only" />
          <button className="btn-primary shrink-0" disabled={busy === "message" || !body.trim()}>{busy === "message" ? <LoaderCircle className="animate-spin" size={17} /> : <MessageCircle size={17} />}Send</button>
        </form>
      )}
    </section>
  );
}
