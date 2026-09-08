import "./globals.css";

export const metadata = {
  title: "Denial Navigator AI - Damco Demo",
  description: "Synthetic denied-claim decision workflow demo",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
