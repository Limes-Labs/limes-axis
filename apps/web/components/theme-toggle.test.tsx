import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeToggle } from "@/components/theme-toggle";
import { THEME_STORAGE_KEY } from "@/lib/theme";
import { ThemeProvider } from "@/providers/theme-provider";

function stubSystemScheme(dark: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: dark,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderToggle() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  stubSystemScheme(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.theme;
});

describe("ThemeToggle", () => {
  it("exposes the current preference in the trigger name", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderToggle();

    expect(screen.getByRole("button", { name: "Color theme: Dark" })).toHaveAttribute(
      "aria-haspopup",
      "menu",
    );
  });

  it("offers System, Light and Dark as a radio group with the current one checked", async () => {
    const user = userEvent.setup();
    renderToggle();

    await user.click(screen.getByRole("button", { name: "Color theme: System" }));

    const group = screen.getByRole("group", { name: "Color theme" });
    expect(group).toBeInTheDocument();
    const options = screen.getAllByRole("menuitemradio");
    expect(options.map((option) => option.textContent)).toEqual(["System", "Light", "Dark"]);
    expect(screen.getByRole("menuitemradio", { name: "System" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("switches to Dark and can return to System", async () => {
    const user = userEvent.setup();
    renderToggle();

    await user.click(screen.getByRole("button", { name: "Color theme: System" }));
    await user.click(screen.getByRole("menuitemradio", { name: "Dark" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    await user.click(screen.getByRole("button", { name: "Color theme: Dark" }));
    expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(screen.getByRole("menuitemradio", { name: "System" }));

    // The OS prefers light here, so returning to System resolves to light.
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("button", { name: "Color theme: System" })).toBeInTheDocument();
  });
});
