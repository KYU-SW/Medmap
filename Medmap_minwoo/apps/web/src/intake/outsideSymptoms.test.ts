import { describe, expect, it } from "vitest";
import { sourcePhrase } from "./outsideSymptoms";

describe("sourcePhrase", () => {
  const text = "어제부터 머리가 아프고 열이 38도까지 났어요. 기침은 없어요.";
  it("widens the rules' evidence to whole words", () => {
    expect(sourcePhrase(text, "머리가 아프")).toBe("머리가 아프고");
    expect(sourcePhrase(text, "기침은 없")).toBe("기침은 없어요");
  });
  it("takes the next word after a very short one", () => {
    expect(sourcePhrase(text, "열이 ")).toBe("열이 38도까지");
  });
  it("keeps evidence it cannot find, such as the rules' rewritten copy", () => {
    expect(sourcePhrase("배 아픔", "배 아파")).toBe("배 아파");
  });
});
