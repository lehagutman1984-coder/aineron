"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Network, FileText, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { getProjectGraph } from "@/lib/api/client";
import type { GraphNode, GraphEdge } from "@/lib/api/types";
import { useEffect, useRef } from "react";

export default function ProjectGraphPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id, 10);

  const { data, isLoading, error } = useQuery({
    queryKey: ["project-graph", projectId],
    queryFn: () => getProjectGraph(projectId),
    staleTime: 60 * 1000,
  });

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex shrink-0 items-center gap-3 border-b border-[rgba(13,13,13,0.08)] px-5 py-3 dark:border-[rgba(255,255,255,0.07)]"
        style={{ background: "var(--surface, #fff)" }}
      >
        <Link
          href={`/projects/${id}`}
          className="flex items-center gap-1.5 text-[14px] text-[rgba(13,13,13,0.50)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)]"
        >
          <ArrowLeft size={13} />
          Проект
        </Link>
        <span className="text-[rgba(13,13,13,0.20)]">/</span>
        <div className="flex items-center gap-2">
          <Network size={16} className="text-[#D97757]" />
          <span className="text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            Граф знаний
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden">
        {isLoading && (
          <div className="flex h-full items-center justify-center text-[rgba(13,13,13,0.40)]">
            Вычисление схожести файлов...
          </div>
        )}

        {error && (
          <div className="p-6 text-[15px] text-[#e74c3c]">
            Не удалось загрузить граф. Убедитесь, что база знаний содержит проиндексированные файлы.
          </div>
        )}

        {data && data.nodes.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
            <Network size={36} className="text-[rgba(13,13,13,0.20)] dark:text-[rgba(236,236,236,0.18)]" />
            <p className="text-[16px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.42)]">
              Нет проиндексированных файлов. Загрузите файлы в базу знаний и дождитесь
              завершения индексации.
            </p>
            <Link
              href={`/projects/${id}`}
              className="text-[15px] font-medium text-[#D97757] hover:underline"
            >
              Перейти к базе знаний
            </Link>
          </div>
        )}

        {data && data.nodes.length > 0 && (
          <GraphCanvas nodes={data.nodes} edges={data.edges} />
        )}
      </div>

      {data && (
        <div
          className="shrink-0 border-t border-[rgba(13,13,13,0.06)] px-5 py-2 text-[13px] text-[rgba(13,13,13,0.40)] dark:border-[rgba(255,255,255,0.06)]"
          style={{ background: "var(--surface, #fff)" }}
        >
          {data.nodes.length} файлов · {data.edges.length} связей ·
          порог схожести 75%
        </div>
      )}
    </div>
  );
}

// ── Force-directed graph (canvas-based, no external lib) ──────────────────────
interface NodeSim extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

function GraphCanvas({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;

    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width = W;
    canvas.height = H;

    // Init positions
    const sim: NodeSim[] = nodes.map((n, i) => ({
      ...n,
      x: W / 2 + 150 * Math.cos((2 * Math.PI * i) / nodes.length),
      y: H / 2 + 150 * Math.sin((2 * Math.PI * i) / nodes.length),
      vx: 0,
      vy: 0,
    }));
    const nodeMap = new Map(sim.map((n) => [n.id, n]));

    const REPEL = 4000;
    const ATTRACT = 0.02;
    const CENTER = 0.005;
    const DAMPING = 0.85;

    let frame = 0;
    let animId: number;

    function tick() {
      // Repulsion
      for (let i = 0; i < sim.length; i++) {
        for (let j = i + 1; j < sim.length; j++) {
          const a = sim[i], b = sim[j];
          const dx = b.x - a.x, dy = b.y - a.y;
          const d2 = dx * dx + dy * dy + 1;
          const f = REPEL / d2;
          a.vx -= f * dx; a.vy -= f * dy;
          b.vx += f * dx; b.vy += f * dy;
        }
      }
      // Attraction along edges
      for (const e of edges) {
        const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const strength = ATTRACT * e.weight;
        a.vx += dx * strength; a.vy += dy * strength;
        b.vx -= dx * strength; b.vy -= dy * strength;
      }
      // Center gravity
      for (const n of sim) {
        n.vx += (W / 2 - n.x) * CENTER;
        n.vy += (H / 2 - n.y) * CENTER;
        n.vx *= DAMPING; n.vy *= DAMPING;
        n.x += n.vx; n.y += n.vy;
      }

      ctx.clearRect(0, 0, W, H);

      // Draw edges
      ctx.lineWidth = 1;
      for (const e of edges) {
        const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
        if (!a || !b) continue;
        const alpha = Math.min(1, e.weight * 0.8 + 0.15);
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = "#D97757";
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }

      // Draw nodes
      ctx.globalAlpha = 1;
      for (const n of sim) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, 18, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(217,119,87,0.12)";
        ctx.fill();
        ctx.strokeStyle = "#D97757";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = "#1A1A1A";
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const label = n.label.length > 14 ? n.label.slice(0, 12) + "…" : n.label;
        ctx.fillText(label, n.x, n.y + 28);
      }

      frame++;
      if (frame < 300) animId = requestAnimationFrame(tick);
    }

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [nodes, edges]);

  return (
    <canvas
      ref={canvasRef}
      className="block h-full w-full"
      style={{ cursor: "default" }}
    />
  );
}
