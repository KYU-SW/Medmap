import { describe, expect, it } from "vitest";
import { decryptSummary, encryptSummary, keyDigits, newKeyNumber, QR_PREFIX } from "./qrCrypto";

const SUMMARY = "기본 정보: 34세 / 여성\n증상: 복통 · 어제부터 · 심함\n복용약: 타이레놀 500mg\n알레르기: 페니실린";

describe("qrCrypto", () => {
  it("makes a new 12-digit number each time", () => {
    const number = newKeyNumber();
    expect(number).toMatch(/^\d{4}-\d{4}-\d{4}$/);
    expect(newKeyNumber()).not.toBe(number);
  });

  it("opens with the right number, typed any way, and the QR holds no readable text", async () => {
    const number = "4821-0937-5562";
    const qr = await encryptSummary(SUMMARY, number);
    expect(qr.startsWith(QR_PREFIX)).toBe(true);
    expect(qr).toMatch(/^[A-Za-z0-9._-]+$/); // ASCII only: keyboard-like scanners do not break it
    expect(qr).not.toContain("복통");
    expect(await decryptSummary(qr, "4821 0937 5562")).toBe(SUMMARY);
    expect(keyDigits(" 4821-0937-5562 ")).toBe("482109375562");
  });

  it("refuses a wrong number, a changed QR and other text", async () => {
    const qr = await encryptSummary(SUMMARY, "482109375562");
    await expect(decryptSummary(qr, "482109375563")).rejects.toThrow("번호가 맞지 않거나");
    const changed = qr.slice(0, -3) + (qr.endsWith("A") ? "BBB" : "AAA");
    await expect(decryptSummary(changed, "482109375562")).rejects.toThrow();
    await expect(decryptSummary("https://example.com", "482109375562")).rejects.toThrow("MedMap 암호화 QR이 아닙니다");
    await expect(decryptSummary(qr, "1234")).rejects.toThrow("12자리");
  });

  it("fits a long summary in one QR (QR byte mode holds 2,331 bytes at level M)", async () => {
    const long = Array.from({ length: 25 }, (_, i) => `증상 ${i + 1}: 복통 · 10월 ${i + 1}일 · 심함 · 4회 → 2회`).join("\n");
    const qr = await encryptSummary(long, "482109375562");
    expect(qr.length).toBeLessThan(2331);
    expect(await decryptSummary(qr, "482109375562")).toBe(long);
  });

  it("opens the example in docs/QR_FORMAT.md", async () => {
    const qr = "MM1.ebXmsLz-b9SvjxLChiKxwdGuvM2CheJtor8WZf7bI9fneWHaj7zA-04rZpIllrvDM8qaIeXOO4U9vZWf8jedeWeB3qo1EcnxhQcdQrX9lZHt6UB1U47wwrG02d5tCauooWLmv1tSORUPAwcVbrTWKKzNZVgck2c";
    expect(await decryptSummary(qr, "4821-0937-5562")).toBe("기본 정보: 34세 / 여성\n증상: 복통 · 어제부터 · 심함");
  });
});
