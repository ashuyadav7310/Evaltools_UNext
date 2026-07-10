function splitFeedbackLine(line: string) {
  const cleaned = line.replace(/\*\*|__/g, "").replace(/^\d+[\.)]\s*/, "").trim();
  const separator = cleaned.includes(" - ") ? " - " : cleaned.includes(" – ") ? " – " : "";
  if (!separator) return { title: cleaned, body: "" };
  const [title, ...rest] = cleaned.split(separator);
  return { title, body: rest.join(separator) };
}

export function FeedbackCards({ text, color }: { text?: string | null; color: "green" | "orange" }) {
  const lines = (text || "").split("\n").map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return <p className="text-sm text-muted-foreground">No feedback recorded.</p>;
  const theme = color === "green" ? "border-l-emerald-500 bg-emerald-50" : "border-l-amber-500 bg-amber-50";
  return (
    <div className="space-y-3">
      {lines.map((line, index) => {
        const item = splitFeedbackLine(line);
        return (
          <div key={`${item.title}-${index}`} className={`rounded-lg border border-l-4 p-4 ${theme}`}>
            <div className="text-sm font-semibold text-slate-900">{item.title}</div>
            {item.body ? <div className="mt-1 text-sm text-slate-600">{item.body}</div> : null}
          </div>
        );
      })}
    </div>
  );
}

export function SkillFeedbackCards({ text }: { text?: string | null }) {
  const normalized = (text || "").replace(/\*\*|__/g, "").trim();
  const lines = normalized.split(/\r?\n/).map((l) => l.replace(/^[-*\s\d\.)]+/, "").trim()).filter(Boolean);
  if (!lines.length) return <p className="text-sm text-muted-foreground">No skill feedback available.</p>;
  return (
    <div className="space-y-3">
      {lines.map((line, index) => {
        // Prefer separators: " - ", " – ", "—", ":"
        const sepMatch = line.match(/\s(?:-|–|—)\s|:/);
        let title = line;
        let body = "";
        if (sepMatch) {
          const sep = sepMatch[0];
          const parts = line.split(sep);
          title = parts.shift()!.trim();
          body = parts.join(sep).trim();
        }
        return (
          <div key={`${title}-${index}`} className="rounded-lg border border-l-4 border-l-blue-500 bg-blue-50 p-4">
            <div className="text-sm font-semibold text-slate-900">{title}</div>
            <div className="mt-1 text-sm text-slate-600">{body}</div>
          </div>
        );
      })}
    </div>
  );
}

export function splitImprovements(text?: string | null) {
  const improvements = text || "";
  const marker = /(?:\*{0,2}\s*(?:Score\s*Justifications|Skill\s*Feedback|Rubric\s*(?:Wise|wise)?\s*Feedback|Rubric-wise\s*Feedback)\s*:\s*\*{0,2})/i;
  const parts = improvements.split(marker);
  const main = (parts[0] || "")
    .replace(/^\s*\*{0,2}\s*(?:Skill\s*Feedback|Rubric\s*(?:Wise|wise)?\s*Feedback|Rubric-wise\s*Feedback)\s*:?\s*\*{0,2}\s*$/gim, "")
    .trim();
  return { main, rubric: parts.slice(1).join("\n").trim() };
}
