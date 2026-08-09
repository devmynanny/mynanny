"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import {
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
} from "lucide-react";
import { useEffect, useState } from "react";

type Conversation = {
  id: number;
  channel: "whatsapp" | "telegram";
  external_id: string;
  user_id?: number | null;
  user_name?: string | null;
  user_role?: string | null;
  last_message_at?: string | null;
  last_inbound_at?: string | null;
  unread_count: number;
  last_message_preview?: string | null;
  last_message_direction?: string | null;
};
type Message = {
  id: number;
  direction: "inbound" | "outbound";
  body: string;
  status: string;
  error_message?: string | null;
  created_at: string;
};
type Thread = { conversation: Conversation; results: Message[] };

export default function CommunicatorPage() {
  return (
    <AuthenticatedPage>
      {(role) =>
        role !== "admin" ? (
          <div className="card mx-auto max-w-xl p-8 text-center">
            <h1 className="text-2xl font-bold">Team access only</h1>
          </div>
        ) : (
          <Communicator />
        )
      }
    </AuthenticatedPage>
  );
}

function Communicator() {
  const [rows, setRows] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [thread, setThread] = useState<Thread | null>(null);
  const [query, setQuery] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [openedAt] = useState(() => Date.now());
  async function loadList(preferredId?: number) {
    const data = await apiJson<{ results: Conversation[] }>(
      "/admin/conversations",
    );
    setRows(data.results || []);
    setSelectedId(
      (current) => preferredId || current || data.results?.[0]?.id || null,
    );
  }
  async function loadThread(id: number) {
    const data = await apiJson<Thread>(`/admin/conversations/${id}/messages`);
    setThread(data);
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, unread_count: 0 } : row)),
    );
  }
  useEffect(() => {
    const userId = Number(
      new URLSearchParams(window.location.search).get("user"),
    );
    const channel =
      new URLSearchParams(window.location.search).get("channel") || "whatsapp";
    const start = async () => {
      try {
        let preferredId: number | undefined;
        if (Number.isFinite(userId) && userId > 0) {
          const opened = await apiJson<{ conversation_id: number }>(
            "/admin/conversations/open",
            {
              method: "POST",
              body: JSON.stringify({ user_id: userId, channel }),
            },
          );
          preferredId = opened.conversation_id;
        }
        await loadList(preferredId);
      } catch (err) {
        setMessage(
          err instanceof Error ? err.message : "Unable to load conversations.",
        );
      } finally {
        setLoading(false);
      }
    };
    void start();
  }, []);
  useEffect(() => {
    if (!selectedId) return;
    apiJson<Thread>(`/admin/conversations/${selectedId}/messages`)
      .then((data) => {
        setThread(data);
        setRows((current) =>
          current.map((row) =>
            row.id === selectedId ? { ...row, unread_count: 0 } : row,
          ),
        );
      })
      .catch((err) =>
        setMessage(
          err instanceof Error ? err.message : "Unable to load messages.",
        ),
      );
  }, [selectedId]);
  async function send() {
    if (!selectedId || !body.trim()) return;
    setSending(true);
    setMessage("");
    try {
      await apiJson(`/admin/conversations/${selectedId}/reply`, {
        method: "POST",
        body: JSON.stringify({ body: body.trim() }),
      });
      setBody("");
      await loadThread(selectedId);
      await loadList(selectedId);
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to send message.",
      );
    } finally {
      setSending(false);
    }
  }
  const filtered = rows.filter((row) =>
    `${row.user_name || ""} ${row.external_id} ${row.last_message_preview || ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const blocked =
    thread?.conversation.channel === "whatsapp" &&
    (!thread.conversation.last_inbound_at ||
      openedAt - new Date(thread.conversation.last_inbound_at).getTime() >
        86_400_000);
  return (
    <div className="mx-auto max-w-[1450px]">
      <div className="eyebrow">Customer communication</div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-4xl sm:text-5xl">Communicator.</h1>
          <p className="mt-3 text-[var(--muted)]">
            WhatsApp and Telegram conversations with parents and nannies.
          </p>
        </div>
        <button
          className="btn-secondary"
          onClick={() => void loadList(selectedId || undefined)}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>
      {message && (
        <div className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
          {message}
        </div>
      )}
      <div className="card mt-7 grid min-h-[680px] overflow-hidden lg:grid-cols-[360px_1fr]">
        <aside className="border-b border-[var(--line)] lg:border-b-0 lg:border-r">
          <label className="relative m-4 block">
            <Search
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
              size={17}
            />
            <input
              className="field !pl-11"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search conversations"
            />
          </label>
          <div className="max-h-[610px] overflow-auto px-3 pb-3">
            {loading ? (
              <LoaderCircle className="mx-auto mt-16 animate-spin" />
            ) : filtered.length ? (
              filtered.map((row) => (
                <button
                  key={row.id}
                  onClick={() => setSelectedId(row.id)}
                  className={`mb-2 w-full rounded-2xl p-4 text-left transition ${selectedId === row.id ? "bg-[var(--blue-pale)]" : "hover:bg-slate-50"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-bold">
                        {row.user_name || row.external_id}
                      </div>
                      <div className="mt-1 text-xs capitalize text-[var(--muted)]">
                        {row.user_role || "Unknown contact"}
                      </div>
                    </div>
                    {row.unread_count > 0 && (
                      <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-[var(--coral)] px-1.5 text-xs font-bold text-white">
                        {row.unread_count}
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <Channel channel={row.channel} />
                    <span className="text-[10px] text-slate-400">
                      {formatTime(row.last_message_at)}
                    </span>
                  </div>
                  <p className="mt-2 truncate text-xs text-[var(--muted)]">
                    {row.last_message_direction === "outbound" ? "You: " : ""}
                    {row.last_message_preview || "No messages yet"}
                  </p>
                </button>
              ))
            ) : (
              <div className="p-8 text-center text-sm text-[var(--muted)]">
                No conversations found.
              </div>
            )}
          </div>
        </aside>
        <section className="flex min-h-[680px] min-w-0 flex-col">
          {thread ? (
            <>
              <header className="border-b border-[var(--line)] p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold">
                      {thread.conversation.user_name ||
                        thread.conversation.external_id}
                    </h2>
                    <div className="mt-1 text-sm text-[var(--muted)]">
                      {thread.conversation.external_id}
                    </div>
                  </div>
                  <Channel channel={thread.conversation.channel} />
                </div>
              </header>
              <div className="flex-1 space-y-3 overflow-auto bg-slate-50/70 p-5">
                {thread.results.length ? (
                  thread.results.map((item) => (
                    <div
                      key={item.id}
                      className={`flex ${item.direction === "outbound" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-sm ${item.direction === "outbound" ? "bg-[var(--blue-dark)] text-white" : "border border-[var(--line)] bg-white"}`}
                      >
                        <p className="whitespace-pre-wrap leading-6">
                          {item.body}
                        </p>
                        <div
                          className={`mt-1 text-[10px] ${item.direction === "outbound" ? "text-white/55" : "text-slate-400"}`}
                        >
                          {formatTime(item.created_at)}
                          {item.status === "failed" ? " · failed" : ""}
                        </div>
                        {item.error_message && (
                          <div className="mt-2 text-xs text-red-300">
                            {item.error_message}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
                    No messages in this conversation yet.
                  </div>
                )}
              </div>
              <footer className="border-t border-[var(--line)] p-4">
                {blocked && (
                  <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                    This WhatsApp conversation is outside the 24-hour reply
                    window. The customer must message first before a free-form
                    reply can be sent.
                  </div>
                )}
                <div className="flex items-end gap-3">
                  <textarea
                    className="field min-h-12 flex-1 resize-none"
                    rows={2}
                    value={body}
                    disabled={blocked || sending}
                    onChange={(event) => setBody(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void send();
                      }
                    }}
                    placeholder="Write a reply..."
                  />
                  <button
                    className="btn-primary !px-4"
                    disabled={blocked || sending || !body.trim()}
                    onClick={() => void send()}
                  >
                    {sending ? (
                      <LoaderCircle className="animate-spin" size={17} />
                    ) : (
                      <Send size={17} />
                    )}
                    Send
                  </button>
                </div>
              </footer>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center p-8 text-center">
              <div>
                <MessageCircle className="mx-auto text-slate-300" size={48} />
                <h2 className="mt-4 text-xl font-bold">
                  Select a conversation
                </h2>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Message history and reply controls will appear here.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Channel({ channel }: { channel: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-bold capitalize ${channel === "whatsapp" ? "bg-emerald-100 text-emerald-800" : "bg-sky-100 text-sky-800"}`}
    >
      {channel}
    </span>
  );
}
function formatTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" });
}
