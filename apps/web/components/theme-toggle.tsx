"use client";

import { useSyncExternalStore } from "react";
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useStrings } from "@/providers/locale-provider";
import { isThemePreference, type ThemePreference } from "@/lib/theme";
import { useTheme } from "@/providers/theme-provider";

const THEME_OPTIONS: { value: ThemePreference; icon: LucideIcon }[] = [
  { value: "system", icon: Monitor },
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
];

const subscribeNoop = () => () => {};

/**
 * Three-way color theme control for the topbar icon cluster: System, Light or
 * Dark as a `menuitemradio` group, so "System" is always reachable again and
 * the current choice is exposed through `aria-checked` and the trigger name.
 *
 * The stored preference is only known on the client, so until hydration the
 * trigger shows the resolved theme through CSS (`dark:` variant) and a generic
 * name; server and client markup therefore match.
 */
export function ThemeToggle() {
  const strings = useStrings();
  const { theme, setTheme } = useTheme();
  const copy = strings.shell.theme;
  const hydrated = useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
  const current = THEME_OPTIONS.find((option) => option.value === theme) ?? THEME_OPTIONS[0];
  const label = hydrated ? copy.triggerLabel(copy.options[current.value]) : copy.trigger;
  const CurrentIcon = current.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button aria-label={label} className="icon-button" title={label} type="button">
          {hydrated ? (
            <CurrentIcon aria-hidden="true" size={17} />
          ) : (
            <>
              <Sun aria-hidden="true" className="dark:hidden" size={17} />
              <Moon aria-hidden="true" className="hidden dark:block" size={17} />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{copy.trigger}</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          aria-label={copy.trigger}
          onValueChange={(value) => {
            if (isThemePreference(value)) {
              setTheme(value);
            }
          }}
          value={theme}
        >
          {THEME_OPTIONS.map(({ value, icon: Icon }) => (
            <DropdownMenuRadioItem key={value} value={value}>
              <Icon aria-hidden="true" size={15} />
              {copy.options[value]}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
