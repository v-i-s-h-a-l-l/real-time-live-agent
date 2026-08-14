import type { Metadata } from "next";
import { Fraunces, Source_Sans_3 } from "next/font/google";

import { SessionKeepAlive } from "@/components/auth/SessionKeepAlive";
import "./globals.css";

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-source-sans",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Lumina — Class 10 AI Tutor",
  description:
    "Human-like voice tutoring for Class 10. Start with Mathematics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sourceSans.variable} ${fraunces.variable}`}>
      <body className="antialiased">
        <SessionKeepAlive />
        {children}
      </body>
    </html>
  );
}
