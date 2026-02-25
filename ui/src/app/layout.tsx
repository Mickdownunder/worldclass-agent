import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Operator — Worldclass Agent",
  description: "Mission Control for the autonomous Operator system",
};

export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var k='operator-theme';var d=typeof document!=='undefined'?document:null;if(!d)return;var s=d.documentElement;try{var v=localStorage.getItem(k);if(v==='light'){s.setAttribute('data-theme','light');}else if(v!=='dark'&&typeof window!=='undefined'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches){s.setAttribute('data-theme','light');}else{s.removeAttribute('data-theme');}}catch(e){}})();`,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
