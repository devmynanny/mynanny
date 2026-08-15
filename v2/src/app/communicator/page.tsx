"use client";

import { AuthenticatedPage } from "@/components/authenticated-page";
import { apiJson } from "@/lib/api";
import {
  LoaderCircle,
  MessageCircle,
  Paperclip,
  Reply,
  RefreshCw,
  Search,
  Send,
  Smile,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

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
  attachments?: Array<{
    url: string;
    content_type: string;
    size?: number;
    name?: string;
  }>;
  reply_to?: {
    id: number;
    direction: "inbound" | "outbound";
    body: string;
    has_attachment: boolean;
  } | null;
  created_at: string;
};
type Thread = { conversation: Conversation; results: Message[] };
const EMOJIS = ["😊", "👍", "❤️", "🙏", "😂", "🎉", "✅", "👋", "🤗", "😢", "😮", "👏"];

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
  const [uploading, setUploading] = useState(false);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [showEmoji, setShowEmoji] = useState(false);
  const [message, setMessage] = useState("");
  const [openedAt] = useState(() => Date.now());
  const fileInput = useRef<HTMLInputElement>(null);
  const messageEnd = useRef<HTMLDivElement>(null);
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
  useEffect(() => {
    if (!selectedId) return;
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      void Promise.all([loadList(selectedId), loadThread(selectedId)]).catch(
        () => undefined,
      );
    };
    const interval = window.setInterval(refresh, 3000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [selectedId]);
  useEffect(() => {
    messageEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread?.results.length]);
  async function sendText(text = body.trim(), replyId = replyTo?.id) {
    if (!selectedId || !text) return;
    setSending(true);
    setMessage("");
    try {
      await apiJson(`/admin/conversations/${selectedId}/reply`, {
        method: "POST",
        body: JSON.stringify({ body: text, reply_to_message_id: replyId }),
      });
      setBody("");
      setReplyTo(null);
      setShowEmoji(false);
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
  async function sendFile(file: File) {
    if (!selectedId) return;
    setUploading(true);
    setMessage("");
    const form = new FormData();
    form.set("attachment", file);
    form.set("caption", body.trim());
    if (replyTo) form.set("reply_to_message_id", String(replyTo.id));
    try {
      await apiJson(`/admin/conversations/${selectedId}/attachments`, {
        method: "POST",
        body: form,
      });
      setBody("");
      setReplyTo(null);
      await Promise.all([loadThread(selectedId), loadList(selectedId)]);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Unable to send file.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
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
          <p className="mt-1 text-xs font-bold text-emerald-700">
            Live · checks for new messages every 3 seconds
          </p>
        </div>
        <button
          className="btn-secondary"
          onClick={() =>
            void Promise.all([
              loadList(selectedId || undefined),
              ...(selectedId ? [loadThread(selectedId)] : []),
            ])
          }
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
                      <div className="group flex max-w-[82%] items-center gap-2">
                        {item.direction === "outbound" && (
                          <MessageActions item={item} onReply={setReplyTo} onReact={(emoji) => void sendText(emoji, item.id)} disabled={blocked || sending} />
                        )}
                        <div
                          className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${item.direction === "outbound" ? "bg-[var(--blue-dark)] text-white" : "border border-[var(--line)] bg-white"}`}
                        >
                        {item.reply_to && (
                          <div className={`mb-2 rounded-lg border-l-2 px-3 py-2 text-xs ${item.direction === "outbound" ? "border-white/60 bg-white/10 text-white/75" : "border-[var(--blue)] bg-slate-50 text-[var(--muted)]"}`}>
                            {item.reply_to.body || (item.reply_to.has_attachment ? "Attachment" : "Message")}
                          </div>
                        )}
                        {!!item.attachments?.length && (
                          <div className="mb-2 space-y-2">
                            {item.attachments.map((attachment, index) => (
                              <MessageAttachment
                                key={`${attachment.url}-${index}`}
                                attachment={attachment}
                              />
                            ))}
                          </div>
                        )}
                        {item.body && (
                          <p className="whitespace-pre-wrap leading-6">
                            {item.body}
                          </p>
                        )}
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
                        {item.direction === "inbound" && (
                          <MessageActions item={item} onReply={setReplyTo} onReact={(emoji) => void sendText(emoji, item.id)} disabled={blocked || sending} />
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
                    No messages in this conversation yet.
                  </div>
                )}
                <div ref={messageEnd} />
              </div>
              <footer className="border-t border-[var(--line)] p-4">
                {blocked && (
                  <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                    This WhatsApp conversation is outside the 24-hour reply
                    window. The customer must message first before a free-form
                    reply can be sent.
                  </div>
                )}
                {replyTo && (
                  <div className="mb-3 flex items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-slate-50 px-4 py-3 text-sm">
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-[var(--blue)]">Replying to {replyTo.direction === "outbound" ? "your message" : "contact"}</div>
                      <div className="truncate text-[var(--muted)]">{replyTo.body || (replyTo.attachments?.length ? "Attachment" : "Message")}</div>
                    </div>
                    <button aria-label="Cancel reply" onClick={() => setReplyTo(null)}><X size={18} /></button>
                  </div>
                )}
                {showEmoji && (
                  <div className="mb-3 flex flex-wrap gap-2 rounded-xl border border-[var(--line)] bg-white p-3 shadow-sm">
                    {EMOJIS.map((emoji) => (
                      <button key={emoji} className="rounded-lg p-1.5 text-xl hover:bg-slate-100" onClick={() => setBody((value) => `${value}${emoji}`)}>{emoji}</button>
                    ))}
                  </div>
                )}
                <div className="flex items-end gap-3">
                  <input
                    ref={fileInput}
                    type="file"
                    className="hidden"
                    accept="image/jpeg,image/png,image/webp,audio/*,video/mp4,video/3gpp,.pdf,.txt,.doc,.docx,.xls,.xlsx"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void sendFile(file);
                    }}
                  />
                  <button className="btn-secondary !px-3" title="Add emoji" disabled={blocked || sending || uploading} onClick={() => setShowEmoji((value) => !value)}><Smile size={18} /></button>
                  <button className="btn-secondary !px-3" title="Send a file" disabled={blocked || sending || uploading || thread.conversation.channel !== "whatsapp"} onClick={() => fileInput.current?.click()}>
                    {uploading ? <LoaderCircle className="animate-spin" size={18} /> : <Paperclip size={18} />}
                  </button>
                  <textarea
                    className="field min-h-12 flex-1 resize-none"
                    rows={2}
                    value={body}
                    disabled={blocked || sending || uploading}
                    onChange={(event) => setBody(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        void sendText();
                      }
                    }}
                    placeholder="Write a reply..."
                  />
                  <button
                    className="btn-primary !px-4"
                    disabled={blocked || sending || uploading || !body.trim()}
                    onClick={() => void sendText()}
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

function MessageActions({
  item,
  onReply,
  onReact,
  disabled,
}: {
  item: Message;
  onReply: (message: Message) => void;
  onReact: (emoji: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
      <button
        className="rounded-full bg-white p-2 text-slate-500 shadow-sm hover:text-[var(--blue)]"
        title="Reply"
        disabled={disabled}
        onClick={() => onReply(item)}
      >
        <Reply size={14} />
      </button>
      <div className="relative group/reaction">
        <button
          className="rounded-full bg-white p-2 text-slate-500 shadow-sm hover:text-[var(--blue)]"
          title="Send an emoji response"
          disabled={disabled}
        >
          <Smile size={14} />
        </button>
        <div className="invisible absolute bottom-full z-20 mb-1 flex -translate-x-1/2 gap-1 rounded-full border border-[var(--line)] bg-white p-1 opacity-0 shadow-lg transition group-hover/reaction:visible group-hover/reaction:opacity-100">
          {["👍", "❤️", "😂", "🙏"].map((emoji) => (
            <button
              key={emoji}
              className="rounded-full p-1 text-base hover:bg-slate-100"
              onClick={() => onReact(emoji)}
            >
              {emoji}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function MessageAttachment({
  attachment,
}: {
  attachment: { url: string; content_type: string; size?: number };
}) {
  const src = attachment.url.startsWith("/media/")
    ? `/api${attachment.url}`
    : attachment.url;
  if (attachment.content_type.startsWith("image/")) {
    return (
      <a href={src} target="_blank" rel="noreferrer" className="block">
        {/* Inbound media dimensions are not known until it is loaded. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt="WhatsApp attachment"
          className="max-h-80 w-auto max-w-full rounded-xl object-contain"
          loading="lazy"
        />
      </a>
    );
  }
  if (attachment.content_type.startsWith("audio/")) {
    return (
      <audio className="w-full min-w-64" controls preload="metadata">
        <source src={src} type={attachment.content_type} />
        Your browser cannot play this audio message.
      </audio>
    );
  }
  return (
    <a className="underline" href={src} target="_blank" rel="noreferrer">
      Open attachment
    </a>
  );
}

function formatTime(value?: string | null) {
  if (!value) return "";
  // API timestamps are UTC. Older rows may be serialized without a timezone
  // suffix, so make that UTC assumption explicit before converting to SAST.
  const normalized = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value)
    ? value
    : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("en-ZA", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Africa/Johannesburg",
      });
}
