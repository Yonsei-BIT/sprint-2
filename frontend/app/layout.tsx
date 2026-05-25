import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "장학금 찾기",
  description: "나에게 맞는 장학금을 한눈에",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
