"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { currentUser } from "@/lib/session";

export default function RootPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(currentUser() ? "/corpus-admin" : "/login");
  }, [router]);
  return null;
}
