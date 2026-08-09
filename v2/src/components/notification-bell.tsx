"use client";

import { apiJson } from "@/lib/api";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

export function NotificationBell() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    apiJson<{ unread_count: number }>("/notifications?unread_only=true&limit=1")
      .then((data) => setCount(data.unread_count || 0))
      .catch(() => undefined);
  }, []);
  return <Link href="/notifications" className="relative flex h-10 w-10 items-center justify-center rounded-full bg-white text-[var(--blue-dark)] shadow-sm" aria-label={`${count} unread notifications`}><Bell size={19}/>{count > 0 && <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--coral)] px-1 text-[10px] font-extrabold text-white">{count > 99 ? "99+" : count}</span>}</Link>;
}
