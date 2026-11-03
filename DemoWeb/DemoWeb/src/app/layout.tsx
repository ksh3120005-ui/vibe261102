import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { MessageSquareText } from "lucide-react";

import { Button } from "@/components/ui/button";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DemoWeb 게시판",
  description: "Next.js · shadcn/ui · TypeScript로 만든 게시판",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-muted/30 antialiased`}
      >
        <header className="border-b bg-background">
          <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <MessageSquareText className="size-5" />
              DemoWeb 게시판
            </Link>
            <Button size="sm" asChild>
              <Link href="/posts/new">글쓰기</Link>
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        <footer className="py-8 text-center text-xs text-muted-foreground">
          © DemoWeb · Next.js + shadcn/ui
        </footer>
      </body>
    </html>
  );
}
