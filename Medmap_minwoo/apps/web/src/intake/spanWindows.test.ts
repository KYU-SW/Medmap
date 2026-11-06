import { describe, expect, it } from "vitest";
import { tagLongText, windowStarts, type Piece, type TagWindow } from "./spanWindows";

// One piece per word; a fake model tags words by a table, so each test controls what every window "sees".
function wordsOf(text: string): Piece[] {
  return [...text.matchAll(/\S+/g)].map((match, id) => ({ id, start: match.index!, end: match.index! + match[0].length }));
}
const filler = (count: number, word = "말") => Array.from({ length: count }, () => word).join(" ");

describe("windowStarts", () => {
  it("reads short input in one window and covers long input with overlapping windows", () => {
    expect(windowStarts(126)).toEqual([0]);
    expect(windowStarts(200)).toEqual([0, 74]);
    expect(windowStarts(400)).toEqual([0, 96, 192, 274]);
  });
});

describe("tagLongText", () => {
  it("tags short input with one call, as before", async () => {
    const text = "딸꾹질 계속 나요";
    const calls: number[][] = [];
    const tag: TagWindow = async (ids) => { calls.push(ids); return ["B-present", "I-present", "I-present"]; };
    const result = await tagLongText(text, wordsOf(text), tag);
    expect(calls).toEqual([[0, 1, 2]]);
    expect(result).toEqual({
      spans: [{ start: 0, end: 9, status: "present", text }], truncated: false, windows: 1, readUpTo: text.length,
    });
  });

  it("finds a symptom at the end of a long text, at its place in the whole text", async () => {
    const text = `${filler(190)} 입냄새 나요`;
    const pieces = wordsOf(text);
    const tag: TagWindow = async (ids) => ids.map((id) => (id === 190 ? "B-present" : id === 191 ? "I-present" : "O"));
    const { spans, windows } = await tagLongText(text, pieces, tag);
    expect(windows).toBe(2);
    expect(spans).toEqual([{ start: pieces[190].start, end: pieces[191].end, status: "present", text: "입냄새 나요" }]);
  });

  it("reports a symptom in the overlap once", async () => {
    const text = `${filler(100)} 멍 들었어요 ${filler(98)}`;
    const tag: TagWindow = async (ids) => ids.map((id) => (id === 100 ? "B-present" : id === 101 ? "I-present" : "O"));
    const { spans } = await tagLongText(text, wordsOf(text), tag);
    expect(spans.map((span) => span.text)).toEqual(["멍 들었어요"]);
  });

  it("takes each side of the cut from the window that read it with more context", async () => {
    // Window 1 reads "없어요" at its edge as present; window 2, which reads the words after it, as absent.
    const text = `${filler(100)} 딸꾹질은 없어요 ${filler(98)}`;
    const tag: TagWindow = async (ids) => ids.map((id) => {
      if (id !== 100 && id !== 101) return "O";
      const late = ids[0] > 0;
      return `${id === 100 ? "B" : "I"}-${late ? "absent" : "present"}`;
    });
    const { spans } = await tagLongText(text, wordsOf(text), tag);
    // The cut lands just before the span (both windows read piece 99 as outside), so the span is window 2's.
    expect(spans).toEqual([expect.objectContaining({ text: "딸꾹질은 없어요", status: "absent" })]);
  });

  it("keeps a span that runs across the cut whole, with the status it started with", async () => {
    // Every piece of the overlap is inside one long span, so there is no outside piece to cut at.
    const text = filler(200, "증상");
    const tag: TagWindow = async (ids) => ids.map((id, index) => {
      if (id < 60 || id > 140) return "O";
      const status = ids[0] > 0 ? "absent" : "present";
      return `${id === 60 || index === 0 ? "B" : "I"}-${status}`;
    });
    const { spans } = await tagLongText(text, wordsOf(text), tag);
    expect(spans).toHaveLength(1);
    expect(spans[0].status).toBe("present");
    expect(spans[0].text.split(" ")).toHaveLength(81);
  });

  it("runs the model on one window at a time, never two at once", async () => {
    const text = filler(400);
    let running = 0;
    let most = 0;
    const order: number[] = [];
    const tag: TagWindow = async (ids) => {
      running += 1;
      most = Math.max(most, running);
      order.push(ids[0]);
      await new Promise((resolve) => setTimeout(resolve, 5));
      running -= 1;
      return ids.map(() => "O");
    };
    const { windows } = await tagLongText(text, wordsOf(text), tag);
    expect(windows).toBe(4);
    expect(most).toBe(1);
    expect(order).toEqual([0, 96, 192, 274]);
  });

  it("stops at the safe maximum and says the rest was not read", async () => {
    const text = filler(30);
    const tag: TagWindow = async (ids) => ids.map(() => "O");
    const result = await tagLongText(text, wordsOf(text), tag, 10, 8, 20);
    expect(result.truncated).toBe(true);
    expect(result.windows).toBe(3);
    expect(text.slice(0, result.readUpTo).split(" ")).toHaveLength(20);
  });
});
