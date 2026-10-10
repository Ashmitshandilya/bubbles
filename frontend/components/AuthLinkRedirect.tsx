"use client";

import { useEffect } from "react";
import { looksLikeAuthReturn } from "../lib/auth-links";

/** If an email link lands on any page other than /callback (for example the home page), hand it to /callback with everything it carries. */
export function AuthLinkRedirect() {
  useEffect(() => {
    const { pathname, search, hash } = window.location;
    if (looksLikeAuthReturn(pathname, search, hash)) window.location.replace(`/callback${search}${hash}`);
  }, []);
  return null;
}
