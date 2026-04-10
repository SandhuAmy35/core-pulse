import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "CORE-PULSE Synergy Dashboard",
  description: "Live productivity and burnout telemetry streaming from the CORE-PULSE mock integration path.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
