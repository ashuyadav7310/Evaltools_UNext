import Image from "next/image";
import Link from "next/link";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-dvh">
      <header className="border-b bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <Image
              src="/comcoachai/UNext_Logo.png"
              alt="UNext"
              width={180}
              height={64}
              priority
              className="h-12 w-auto max-w-[160px] object-contain sm:max-w-[180px]"
            />
          </Link>
          <nav className="flex items-center gap-2 text-sm">
            <Link className="rounded-md border bg-white px-3 py-2 font-medium hover:bg-secondary" href="/admin">
              Admin Center
            </Link>
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 py-6">{children}</div>
    </main>
  );
}
