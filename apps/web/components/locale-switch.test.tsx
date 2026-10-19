import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocaleSwitch } from "@/components/locale-switch";
import { getConsoleLocale } from "@/lib/console-locale";
import { formatTimestamp } from "@/lib/format";
import { LOCALE_COOKIE } from "@/lib/locale";
import { LocaleProvider, useStrings } from "@/providers/locale-provider";

function clearLocaleCookie() {
  document.cookie = `${LOCALE_COOKIE}=; Path=/; Max-Age=0`;
}

afterEach(() => {
  clearLocaleCookie();
  document.documentElement.lang = "";
});

describe("LocaleSwitch", () => {
  it("is a labelled select listing each language in its own name", () => {
    render(
      <LocaleProvider locale="en">
        <LocaleSwitch reload={() => {}} />
      </LocaleProvider>,
    );

    const select = screen.getByRole("combobox", { name: "Language" });
    expect(select).toHaveValue("en");
    expect(select).toHaveAccessibleDescription("Changing the language reloads the console.");
    expect(screen.getByRole("option", { name: "English" })).toHaveAttribute("lang", "en");
    expect(screen.getByRole("option", { name: "Italiano" })).toHaveAttribute("lang", "it");
  });

  it("persists the choice in the locale cookie and reloads", async () => {
    const reload = vi.fn();
    render(
      <LocaleProvider locale="en">
        <LocaleSwitch reload={reload} />
      </LocaleProvider>,
    );

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Language" }), "it");

    expect(document.cookie).toContain(`${LOCALE_COOKIE}=it`);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("does nothing when the current language is chosen again", async () => {
    const reload = vi.fn();
    render(
      <LocaleProvider locale="it">
        <LocaleSwitch reload={reload} />
      </LocaleProvider>,
    );

    const select = screen.getByRole("combobox", { name: "Lingua" });
    expect(select).toHaveValue("it");
    await userEvent.selectOptions(select, "it");

    expect(document.cookie).not.toContain(LOCALE_COOKIE);
    expect(reload).not.toHaveBeenCalled();
  });
});

describe("LocaleProvider", () => {
  function Heading() {
    return <h1>{useStrings().pages.settings.title}</h1>;
  }

  it("serves the Italian catalogue under the it locale", () => {
    render(
      <LocaleProvider locale="it">
        <Heading />
      </LocaleProvider>,
    );
    expect(screen.getByRole("heading", { name: "Impostazioni" })).toBeVisible();
  });

  it("falls back to English outside a provider", () => {
    render(<Heading />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
  });
});

describe("getConsoleLocale", () => {
  it("follows <html lang> so formatted dates match the chosen language", () => {
    const instant = "2026-06-21T16:30:00Z";
    document.documentElement.lang = "en";
    expect(getConsoleLocale()).toBe("en");
    const english = formatTimestamp(instant);

    document.documentElement.lang = "it";
    expect(getConsoleLocale()).toBe("it");
    const italian = formatTimestamp(instant);

    expect(english).toMatch(/Jun/);
    expect(italian).toMatch(/giu/);
  });

  it("falls back to English for an unsupported document language", () => {
    document.documentElement.lang = "fr";
    expect(getConsoleLocale()).toBe("en");
  });
});
