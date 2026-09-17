/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    let backend =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_BACKEND_URL;

    if (!backend || backend.includes("localhost") || backend.includes("127.0.0.1")) {
      if (process.env.NODE_ENV === "production" || process.env.VERCEL) {
        backend = "https://logistics-hackathon.onrender.com";
      } else {
        backend = "http://127.0.0.1:8000";
      }
    }

    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
