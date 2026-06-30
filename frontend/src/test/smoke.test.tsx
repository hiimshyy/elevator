import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

// Trivial smoke test — confirms the test toolchain (Vitest + jsdom +
// @testing-library/react + @testing-library/jest-dom) is wired correctly.
function Hello({ name }: { name: string }) {
  return <p data-testid="greeting">Hello, {name}!</p>;
}

describe("smoke test", () => {
  it("renders a React component in jsdom", () => {
    render(<Hello name="Elevator PDM" />);
    const el = screen.getByTestId("greeting");
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent("Hello, Elevator PDM!");
  });
});
