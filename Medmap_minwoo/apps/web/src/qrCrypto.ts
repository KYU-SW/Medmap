// Encrypted visit-summary QR (2026-11-11 user decision: QR holds only ciphertext; the patient tells the doctor a
// 12-digit number). Standalone on purpose: only the platform's WebCrypto and CompressionStream, no app imports, so a
// teammate's doctor screen can copy this file as it is. The format is written down in docs/QR_FORMAT.md.
//
//   MM1.<base64url( salt[16] | iv[12] | AES-256-GCM( deflate-raw( UTF-8 summary ) ) )>
//   key = PBKDF2-SHA256(the 12 digits as ASCII, salt, 600,000 rounds) → 256 bits
//
// 12 digits are about 40 bits; the 600,000 rounds make each guess slow, so trying them all from a leaked QR photo
// takes far longer than the visit matters. A new number and salt are made for every QR.

export const QR_PREFIX = "MM1.";
export const KEY_DIGITS = 12;
export const PBKDF2_ROUNDS = 600_000;

const encoder = new TextEncoder();

/** A fresh random number for one QR, shown as "4821-0937-5562". */
export function newKeyNumber(): string {
  const digits = Array.from(crypto.getRandomValues(new Uint32Array(KEY_DIGITS)), (value) => value % 10).join("");
  return digits.replace(/(\d{4})(?=\d)/g, "$1-");
}

/** The digits alone, whatever was typed around them ("4821 0937-5562" → "482109375562"). */
export const keyDigits = (number: string) => number.replace(/\D/g, "");

async function keyFrom(number: string, salt: Uint8Array<ArrayBuffer>): Promise<CryptoKey> {
  const digits = keyDigits(number);
  if (digits.length !== KEY_DIGITS) throw new Error(`번호는 숫자 ${KEY_DIGITS}자리여야 합니다.`);
  const base = await crypto.subtle.importKey("raw", encoder.encode(digits), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: PBKDF2_ROUNDS },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

async function pipe(data: Uint8Array<ArrayBuffer>, stream: CompressionStream | DecompressionStream): Promise<Uint8Array<ArrayBuffer>> {
  const out = new Blob([data]).stream().pipeThrough(stream);
  return new Uint8Array(await new Response(out).arrayBuffer());
}

const toBase64Url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromBase64Url = (text: string) =>
  Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), (char) => char.charCodeAt(0));

export async function encryptSummary(summary: string, number: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const packed = await pipe(encoder.encode(summary), new CompressionStream("deflate-raw"));
  const sealed = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await keyFrom(number, salt), packed));
  return QR_PREFIX + toBase64Url(new Uint8Array([...salt, ...iv, ...sealed]));
}

/** The summary, or an Error whose message can be shown as it is (wrong number, not a MedMap QR). */
export async function decryptSummary(qrText: string, number: string): Promise<string> {
  const text = qrText.trim();
  if (!text.startsWith(QR_PREFIX)) throw new Error("MedMap 암호화 QR이 아닙니다.");
  let bytes: Uint8Array<ArrayBuffer>;
  try {
    bytes = fromBase64Url(text.slice(QR_PREFIX.length));
  } catch {
    throw new Error("QR 내용이 깨졌습니다. 다시 읽어 주세요.");
  }
  if (bytes.length < 16 + 12 + 16) throw new Error("QR 내용이 깨졌습니다. 다시 읽어 주세요.");
  const key = await keyFrom(number, bytes.slice(0, 16));
  let packed: ArrayBuffer;
  try {
    packed = await crypto.subtle.decrypt({ name: "AES-GCM", iv: bytes.slice(16, 28) }, key, bytes.slice(28));
  } catch {
    // GCM checks the whole message: a wrong number and a changed QR both end here.
    throw new Error("번호가 맞지 않거나 QR이 바뀌었습니다.");
  }
  return new TextDecoder().decode(await pipe(new Uint8Array(packed), new DecompressionStream("deflate-raw")));
}
