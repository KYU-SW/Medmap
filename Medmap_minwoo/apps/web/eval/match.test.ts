import { describe, expect, it } from "vitest";
import { pairByPlace } from "./match";

const r = (start: number, end: number) => ({ start, end });

describe("pairByPlace", () => {
  it("pairs only parts that overlap an answer", () => {
    expect(pairByPlace([r(0, 5)], [r(10, 15)])).toEqual({ pairs: [], duplicates: [], unmatched: [0] });
  });

  it("gives one answer to the part that overlaps it most; another part over it is a duplicate", () => {
    expect(pairByPlace([r(0, 10)], [r(0, 3), r(0, 9)])).toEqual({ pairs: [[0, 1]], duplicates: [0], unmatched: [] });
  });

  it("lets one long part pair with only one of two answers it covers", () => {
    // The part covers answer 0 by 5 and answer 1 by 3: it takes answer 0, and answer 1 stays missed.
    expect(pairByPlace([r(0, 5), r(6, 9)], [r(0, 9)])).toEqual({ pairs: [[0, 0]], duplicates: [], unmatched: [] });
  });

  it("breaks ties by the earlier answer, then the earlier part", () => {
    expect(pairByPlace([r(0, 4), r(4, 8)], [r(2, 6)]).pairs).toEqual([[0, 0]]);
    expect(pairByPlace([r(0, 4)], [r(0, 4), r(0, 4)])).toEqual({ pairs: [[0, 0]], duplicates: [1], unmatched: [] });
  });
});
