import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import "./globals.css";
export const metadata: Metadata = {
  title: "VayuOps · Air Quality Intelligence",
  description:
    "Explore Indian city PM2.5 forecasts, model performance, and data drift.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
