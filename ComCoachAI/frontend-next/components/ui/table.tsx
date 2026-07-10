import { cn } from "@/lib/utils";

export function DataTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">No data available.</p>;
  const columns = Object.keys(rows[0]);
  return (
    <div className="w-full overflow-x-auto rounded-lg border bg-card">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-secondary">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-3 py-2 font-semibold">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className={cn(rowIndex % 2 ? "bg-secondary/35" : "bg-card")}>
              {columns.map((column) => (
                <td key={column} className="px-3 py-2 align-top">
                  {String(row[column] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
