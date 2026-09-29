import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RoomFit Copilot",
  description:
    "AI furniture shopping assistant with hybrid RAG, tool-calling agent, and SSE streaming.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
