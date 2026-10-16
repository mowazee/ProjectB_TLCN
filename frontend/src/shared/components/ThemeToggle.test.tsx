import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setThemePreference } from "@/shared/theme";

import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle (giao diện sáng/tối)", () => {
  afterEach(() => setThemePreference("system"));

  it("chuyển Theo hệ thống -> Sáng -> Tối -> Theo hệ thống, đặt data-theme và lưu lựa chọn", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    const button = () => screen.getByRole("button", { name: /^Giao diện:/ });

    expect(button()).toHaveAccessibleName(/Theo hệ thống/);
    // jsdom không có matchMedia -> "theo hệ thống" coi là sáng
    await user.click(button());
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("theme")).toBe("light");

    await user.click(button());
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(button()).toHaveAccessibleName(/^Giao diện: Tối/);

    await user.click(button());
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("theme")).toBeNull(); // theo hệ thống: không lưu cứng
  });
});
