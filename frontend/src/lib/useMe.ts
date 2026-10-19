"use client";

import { useEffect, useState } from "react";
import { api, type Me } from "./api";

/** Current user (null = visitor). `undefined` while loading. */
export function useMe() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    api<{ user: Me | null }>("/me/session")
      .then((data) => active && setMe(data.user))
      // any failure renders the visitor view
      .catch(() => active && setMe(null));
    return () => {
      active = false;
    };
  }, []);

  return { me };
}
