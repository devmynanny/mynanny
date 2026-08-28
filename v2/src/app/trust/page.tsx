"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import { Award, Check, Plus, RefreshCw, Save, ShieldCheck } from "lucide-react";
import { startTransition, useEffect, useState } from "react";

type Badge = { key: string; label: string; required: boolean; parent_visible: boolean };
type Lookup = { id: number; name: string; is_active: boolean };

export default function TrustPage() {
  return <AuthenticatedPage>{(role) => role === "admin" ? <TrustWorkspace /> : <Denied />}</AuthenticatedPage>;
}

function TrustWorkspace() {
  const [badges, setBadges] = useState<Badge[]>([]);
  const [tags, setTags] = useState<Lookup[]>([]);
  const [qualifications, setQualifications] = useState<Lookup[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true); setMessage("");
    try {
      const [config, tagRows, qualificationRows] = await Promise.all([
        apiJson<{ badges: Badge[] }>("/admin/trust-config"), apiJson<Lookup[]>("/admin/nanny-tags"), apiJson<Lookup[]>("/admin/qualifications"),
      ]);
      setBadges(config.badges); setTags(tagRows); setQualifications(qualificationRows);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load trust configuration."); }
    finally { setLoading(false); }
  };
  useEffect(() => { startTransition(() => { void load(); }); }, []);
  async function saveBadges() {
    try { await apiJson("/admin/trust-config", { method: "PUT", body: JSON.stringify({ badges }) }); setMessage("Badge rules saved."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save badge rules."); }
  }
  async function add(kind: "nanny-tags" | "qualifications") {
    const name = window.prompt(kind === "nanny-tags" ? "New tag name" : "New qualification or specialty");
    if (!name?.trim()) return;
    try { await apiJson(`/admin/${kind}`, { method: "POST", body: JSON.stringify({ name }) }); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to add this item."); }
  }
  async function toggle(kind: "nanny-tags" | "qualifications", row: Lookup) {
    try { await apiJson(`/admin/${kind}/${row.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !row.is_active }) }); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to update this item."); }
  }
  return <div className="mx-auto max-w-[1500px]">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><div className="eyebrow">Trust system</div><h1 className="display mt-2 text-4xl sm:text-5xl">Trust configuration.</h1><p className="mt-3 max-w-3xl text-[var(--muted)]">Control which verified signals matter, what parents can see, and the specialties used for matching.</p></div><button className="btn-secondary" onClick={() => void load()}><RefreshCw size={17}/>Refresh</button></div>
    {message && <div className="mt-6 rounded-2xl bg-[var(--blue-pale)] p-4 font-semibold">{message}</div>}
    {loading ? <div className="card mt-8 p-8">Loading trust settings...</div> : <div className="mt-8 grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
      <section className="card overflow-hidden"><div className="border-b border-[var(--line)] p-6"><div className="flex items-center gap-3"><Award className="text-[var(--blue)]"/><h2 className="text-2xl font-bold">Badge rules</h2></div><p className="mt-2 text-[var(--muted)]">Badges are only earned after the relevant evidence is approved by an administrator.</p></div><div className="grid gap-3 p-6">{badges.map((badge, index) => <div key={badge.key} className="rounded-2xl border border-[var(--line)] p-4 sm:flex sm:items-center sm:justify-between"><div><div className="font-bold">{badge.label}</div><div className="text-sm text-[var(--muted)]">{badge.key.replaceAll("_", " ")}</div></div><div className="mt-3 flex flex-wrap gap-2 sm:mt-0"><Toggle active={badge.required} onClick={() => setBadges((rows) => rows.map((item, i) => i === index ? { ...item, required: !item.required } : item))} labels={["Required", "Optional"]}/><Toggle active={badge.parent_visible} onClick={() => setBadges((rows) => rows.map((item, i) => i === index ? { ...item, parent_visible: !item.parent_visible } : item))} labels={["Parent visible", "Internal only"]}/></div></div>)}</div><div className="border-t border-[var(--line)] p-6"><button className="btn-primary" onClick={() => void saveBadges()}><Save size={18}/>Save badge rules</button></div></section>
      <div className="grid content-start gap-6"><LookupPanel title="Nanny tags" intro="Traits and matching filters shown across profiles." rows={tags} add={() => void add("nanny-tags")} toggle={(row) => void toggle("nanny-tags", row)}/><LookupPanel title="Qualifications & specialties" intro="Training, certifications and care specialties." rows={qualifications} add={() => void add("qualifications")} toggle={(row) => void toggle("qualifications", row)}/></div>
    </div>}
  </div>;
}

function Toggle({ active, onClick, labels }: { active: boolean; onClick: () => void; labels: [string, string] }) { return <button onClick={onClick} className={`rounded-full border px-3 py-2 text-xs font-bold ${active ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-[var(--line)] bg-white text-[var(--muted)]"}`}>{active && <Check className="mr-1 inline" size={13}/>} {active ? labels[0] : labels[1]}</button>; }
function LookupPanel({ title, intro, rows, add, toggle }: { title: string; intro: string; rows: Lookup[]; add: () => void; toggle: (row: Lookup) => void }) { return <section className="card p-6"><div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-bold">{title}</h2><p className="mt-1 text-sm text-[var(--muted)]">{intro}</p></div><button className="btn-quiet !px-3" onClick={add} aria-label={`Add ${title}`}><Plus/></button></div><div className="mt-5 grid gap-2">{rows.map((row) => <button key={row.id} onClick={() => toggle(row)} className={`flex items-center justify-between rounded-xl border p-3 text-left ${row.is_active ? "border-[var(--line)]" : "border-dashed border-slate-300 bg-slate-50 text-[var(--muted)]"}`}><span className="font-semibold">{row.name}</span><span className="text-xs font-bold uppercase">{row.is_active ? "Active" : "Retired"}</span></button>)}</div></section>; }
function Denied() { return <div className="card mx-auto max-w-xl p-8 text-center"><ShieldCheck className="mx-auto"/><h1 className="mt-4 text-2xl font-bold">Superadmin access required</h1></div>; }
