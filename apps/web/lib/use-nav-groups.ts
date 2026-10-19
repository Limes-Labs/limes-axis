"use client";

import { useMemo } from "react";

import { buildNavGroups, type NavGroup } from "@/lib/nav";
import { useStrings } from "@/providers/locale-provider";

/** The grouped navigation labelled in the active locale. */
export function useNavGroups(): NavGroup[] {
  const strings = useStrings();
  return useMemo(() => buildNavGroups(strings), [strings]);
}
