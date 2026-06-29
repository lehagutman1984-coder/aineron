"use client";

import { useQuery } from "@tanstack/react-query";
import { Trophy, Swords, TrendingUp } from "lucide-react";
import Link from "next/link";
import { getArenaLeaderboard } from "@/lib/api/client";
import type { ArenaEntry } from "@/lib/api/types";

export default function ArenaPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["arena-leaderboard"],
    queryFn: getArenaLeaderboard,
  });

  const entries = data?.results ?? [];

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Trophy size={24} className="text-[#f4a017]" />
          <h1 className="text-[24px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
            Model Arena
          </h1>
        </div>
        <p className="text-[14px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.45)]">
          Elo-рейтинг моделей на основе сравнительных поединков. Голосуйте на странице{" "}
          <Link href="/compare" className="text-[#D97757] hover:underline">
            сравнения
          </Link>{" "}
          — рейтинг обновляется автоматически.
        </p>
      </div>

      {isLoading && (
        <div className="text-center py-16 text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.30)]">
          Загрузка рейтинга...
        </div>
      )}

      {error && (
        <div className="rounded-[12px] border border-[rgba(231,76,60,0.25)] bg-[rgba(231,76,60,0.06)] p-4 text-[13px] text-[#e74c3c]">
          Не удалось загрузить рейтинг. Попробуйте позже.
        </div>
      )}

      {!isLoading && entries.length === 0 && !error && (
        <div className="rounded-[12px] border border-dashed border-[rgba(13,13,13,0.15)] px-6 py-12 text-center dark:border-[rgba(255,255,255,0.10)]">
          <Swords size={32} className="mx-auto mb-3 text-[rgba(13,13,13,0.25)] dark:text-[rgba(236,236,236,0.25)]" />
          <p className="text-[14px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.40)]">
            Арена пуста. Сыграйте первый матч на странице{" "}
            <Link href="/compare" className="text-[#D97757] hover:underline">
              сравнения моделей
            </Link>
            .
          </p>
        </div>
      )}

      {entries.length > 0 && (
        <div className="overflow-hidden rounded-[14px] border border-[rgba(13,13,13,0.09)] dark:border-[rgba(255,255,255,0.08)]">
          <table className="w-full text-[13px]">
            <thead>
              <tr
                className="border-b border-[rgba(13,13,13,0.08)] text-left dark:border-[rgba(255,255,255,0.07)]"
                style={{ background: "rgba(13,13,13,0.03)" }}
              >
                <th className="px-4 py-3 font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
                  #
                </th>
                <th className="px-4 py-3 font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
                  Модель
                </th>
                <th className="px-4 py-3 text-right font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
                  Elo
                </th>
                <th className="px-4 py-3 text-right font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
                  Матчей
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, idx) => (
                <ArenaRow key={entry.slug} entry={entry} rank={idx + 1} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {entries.length > 0 && (
        <div className="mt-6 flex justify-center">
          <Link
            href="/compare"
            className="flex items-center gap-2 rounded-[10px] px-5 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "#1A1A1A" }}
          >
            <Swords size={14} />
            Сыграть матч
          </Link>
        </div>
      )}
    </div>
  );
}

function medalColor(rank: number): string {
  if (rank === 1) return "#f4a017";
  if (rank === 2) return "#9ca3af";
  if (rank === 3) return "#cd7f32";
  return "transparent";
}

function ArenaRow({ entry, rank }: { entry: ArenaEntry; rank: number }) {
  const medal = medalColor(rank);
  const isTop3 = rank <= 3;

  return (
    <tr
      className="border-b border-[rgba(13,13,13,0.06)] transition-colors last:border-0 hover:bg-[rgba(13,13,13,0.02)] dark:border-[rgba(255,255,255,0.05)] dark:hover:bg-[rgba(255,255,255,0.03)]"
      style={{ background: isTop3 ? `${medal}08` : undefined }}
    >
      <td className="px-4 py-3 font-bold" style={{ color: medal || "rgba(13,13,13,0.35)" }}>
        {rank}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          {entry.avatar_url ? (
            <img
              src={entry.avatar_url}
              alt={entry.name}
              width={28}
              height={28}
              className="rounded-[6px] object-cover shrink-0"
            />
          ) : (
            <div className="h-7 w-7 shrink-0 rounded-[6px] bg-[rgba(10,124,255,0.12)] flex items-center justify-center">
              <TrendingUp size={12} className="text-[#D97757]" />
            </div>
          )}
          <div>
            <p className="font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">{entry.name}</p>
            {entry.description && (
              <p className="text-[11px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)] line-clamp-1">
                {entry.description}
              </p>
            )}
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-right font-mono font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
        {entry.elo_rating.toFixed(0)}
      </td>
      <td className="px-4 py-3 text-right text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.42)]">
        {entry.elo_matches}
      </td>
    </tr>
  );
}
