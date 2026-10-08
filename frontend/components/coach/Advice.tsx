import type { CoachTask } from "@/lib/coach";

/** The AI writer's advice on a task or play, and the knowledge it drew on, if any. */
export default function Advice({ task }: { task: CoachTask }) {
  if (!task.advice) return null;
  return (
    <div className="mt-2 pl-7 text-sm">
      <p>{task.advice}</p>
      {task.knowledge && task.knowledge.length > 0 && (
        <p className="mt-1 text-xs text-muted">Also from the coach notes: {task.knowledge.map((k) => k.title).join(", ")}</p>
      )}
    </div>
  );
}
