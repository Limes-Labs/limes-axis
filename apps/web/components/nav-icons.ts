import type { ComponentType } from "react";

import {
  Bot,
  Building2,
  Cable,
  FlaskConical,
  Gauge,
  Network,
  ReceiptText,
  Route,
  ScrollText,
  Settings,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import type { NavIcon } from "@/lib/nav";

/** Maps `lib/nav.ts` icon names to lucide components for shell + command menu. */
export const navIconMap: Record<NavIcon, ComponentType<{ size?: number; className?: string }>> = {
  gauge: Gauge,
  network: Network,
  workflow: Workflow,
  bot: Bot,
  route: Route,
  shield: ShieldCheck,
  scroll: ScrollText,
  receipt: ReceiptText,
  flask: FlaskConical,
  cable: Cable,
  building: Building2,
  settings: Settings,
};
