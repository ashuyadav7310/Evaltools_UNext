import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: "/comcoachai",
  env: {
    COMCOACH_API_BASE_URL:
      process.env.COMCOACH_API_BASE_URL || "/api/comcoachai",
    API_BASE_URL: process.env.API_BASE_URL,
  },
};

export default nextConfig;
