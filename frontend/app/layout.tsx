import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Portfolio MVP",
  description: "Personal portfolio dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <div className="border-b border-line bg-panel/60 backdrop-blur sticky top-0 z-10">
          <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
            <Link href="/" className="font-semibold">📈 Portfolio</Link>
            <nav className="flex gap-4 text-sm text-muted">
              <Link href="/" className="hover:text-text">Dashboard</Link>
              <Link href="/holdings" className="hover:text-text">Holdings</Link>
              <Link href="/transactions" className="hover:text-text">Transactions</Link>
              <Link href="/accounts" className="hover:text-text">Accounts</Link>
              <Link href="/performance" className="hover:text-text">Performance</Link>
              <Link href="/analyze" className="hover:text-text">Analyze</Link>
            </nav>
          </div>
        </div>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
