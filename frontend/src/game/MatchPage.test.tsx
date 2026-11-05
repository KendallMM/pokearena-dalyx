import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { formatTime, leaderOf, timeLeftPercent, totalPower } from "./match";
import { MatchPage } from "./MatchPage";

describe("match rules", () => {
  it("adds the power of the cards, including an empty location", () => {
    expect(totalPower([4, 5])).toBe(9);
    expect(totalPower([])).toBe(0);
  });

  it.each([
    [3, 9, "player"],
    [11, 4, "rival"],
    [0, 0, "tie"],
  ])("with rival %i and player %i the leader is %s", (rival, player, leader) => {
    expect(leaderOf(rival, player)).toBe(leader);
  });

  it("formats the time with two digits for the seconds", () => {
    expect(formatTime(18)).toBe("0:18");
    expect(formatTime(5)).toBe("0:05");
  });

  it("keeps the time bar between 0 and 100 percent", () => {
    expect(timeLeftPercent(18, 30)).toBe(60);
    expect(timeLeftPercent(-1, 30)).toBe(0);
    expect(timeLeftPercent(40, 30)).toBe(100);
  });
});

describe("MatchPage", () => {
  it("shows each location with its totals and its leader", () => {
    render(<MatchPage />);

    const first = screen.getByRole("region", { name: "Ubicación 1" });
    expect(first).toHaveAttribute("data-leader", "player");
    expect(within(first).getByText(/Rival:/).parentElement).toHaveTextContent(
      "Rival: 3",
    );
    expect(within(first).getByText(/Tú:/).parentElement).toHaveTextContent("Tú: 9");
    expect(screen.getByRole("region", { name: "Ubicación 2" })).toHaveAttribute(
      "data-leader",
      "tie",
    );
    expect(screen.getByRole("region", { name: "Ubicación 3" })).toHaveAttribute(
      "data-leader",
      "rival",
    );
  });

  it("marks the sides of a location that have no cards", () => {
    render(<MatchPage />);
    const empty = screen.getByRole("region", { name: "Ubicación 2" });
    expect(within(empty).getAllByText("Sin cartas")).toHaveLength(2);
    expect(
      within(screen.getByRole("region", { name: "Ubicación 1" })).queryByText(
        "Sin cartas",
      ),
    ).not.toBeInTheDocument();
  });

  it("offers the three actions as real buttons", () => {
    render(<MatchPage />);
    for (const name of ["Dynamax", "Run", "Confirmar"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("dims only the cards that cost more than the available energy", () => {
    render(<MatchPage />);
    const cards = within(screen.getByRole("list", { name: "Tu mano" })).getAllByRole(
      "listitem",
    );

    expect(cards).toHaveLength(4);
    const dimmed = cards.filter((card) =>
      card.classList.contains("match-card--unplayable"),
    );
    expect(dimmed).toHaveLength(1);
    expect(dimmed[0]).toHaveTextContent("Costo: 7");
    expect(dimmed[0]).toHaveTextContent("No alcanza la energía");
  });
});
