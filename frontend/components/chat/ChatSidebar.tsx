"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PenSquare, Code2, LayoutGrid } from "lucide-react";
import { listChats } from "@/lib/api/client";

export function ChatSidebar() {
  const pathname = usePathname();

  const { data: chats = [] } = useQuery({
    queryKey: ["chats"],
    queryFn: listChats,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  return (
    <aside className="hidden md:flex w-[220px] shrink-0 flex-col border-r border-[rgba(13,13,13,0.10)] bg-white">
      {/* Actions */}
      <div className="flex gap-1.5 p-3 border-b border-[rgba(13,13,13,0.08)]">
        <Link
          href="/models/"
          className="flex flex-1 items-center justify-center gap-1.5 h-8 rounded-[7px] bg-[#0a7cff] px-2 text-[12px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          <PenSquare size={13} />
          Новый чат
        </Link>
        <Link
          href="/models/"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d] transition-colors"
          title="Все модели"
        >
          <LayoutGrid size={14} />
        </Link>
      </div>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto py-1">
        {chats.length === 0 && (
          <div className="px-4 py-10 text-center text-[12px] text-[rgba(13,13,13,0.38)]">
            Нет чатов.
            <br />
            <Link href="/models/" className="mt-1 inline-block text-[#0a7cff] hover:underline">
              Выбрать модель
            </Link>
          </div>
        )}

        {chats.map((chat) => {
          const active =
            pathname === `/chat/${chat.id}/` || pathname === `/chat/${chat.id}`;
          return (
            <Link
              key={chat.id}
              href={`/chat/${chat.id}/`}
              className={[
                "flex items-start gap-2 px-3 py-2.5 transition-colors",
                active
                  ? "bg-[rgba(10,124,255,0.07)]"
                  : "hover:bg-[rgba(13,13,13,0.04)]",
              ].join(" ")}
            >
              {/* Avatar */}
              {chat.network.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={chat.network.avatar}
                  alt={chat.network.name}
                  width={22}
                  height={22}
                  className="mt-px shrink-0 rounded-[5px] object-cover"
                />
              ) : (
                <div className="mt-px flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.12)]">
                  <Code2 size={12} className="text-[#0a7cff]" />
                </div>
              )}

              {/* Text */}
              <div className="min-w-0 flex-1">
                <p
                  className={[
                    "truncate text-[12px] font-medium leading-4",
                    active ? "text-[#0a7cff]" : "text-[#0d0d0d]",
                  ].join(" ")}
                >
                  {chat.network.name}
                </p>
                {chat.last_message ? (
                  <p className="mt-0.5 truncate text-[11px] leading-3.5 text-[rgba(13,13,13,0.42)]">
                    {chat.last_message.role === "user" ? "Вы: " : ""}
                    {chat.last_message.preview}
                  </p>
                ) : (
                  <p className="mt-0.5 text-[11px] leading-3.5 text-[rgba(13,13,13,0.3)]">
                    Пустой чат
                  </p>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
