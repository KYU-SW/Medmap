"""STEP15 v2 - external source fetcher (no DDXPlus access).
Usage: python s15v2_fetch.py <source_id> <url>
Saves raw html/pdf + extracted text + sha256 into data/disease_profiles_v2/raw/.
No blocking-bypass: plain GET with a descriptive UA; on 403/captcha we record BLOCKED."""
import sys, hashlib, re, json, datetime, pathlib, subprocess
from html.parser import HTMLParser

RAW = pathlib.Path("data/disease_profiles_v2/raw")
UA = "MedMap-research-fetch/0.1 (academic; contact: <email>)"

class Text(HTMLParser):
    SKIP = {"script","style","noscript","nav","footer","header","svg"}
    def __init__(s): super().__init__(); s.out=[]; s.skip=0
    def handle_starttag(s,t,a):
        if t in s.SKIP: s.skip+=1
        if t in ("p","div","li","h1","h2","h3","h4","h5","tr","br","section","td","th"): s.out.append("\n")
    def handle_endtag(s,t):
        if t in s.SKIP and s.skip>0: s.skip-=1
    def handle_data(s,d):
        if not s.skip: s.out.append(d)
    def text(s): return re.sub(r"\n\s*\n+","\n",re.sub(r"[ \t]+"," ","".join(s.out))).strip()

def main(sid, url):
    RAW.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    r = subprocess.run(["curl","-sSL","-A",UA,"--max-time","60","-o",str(RAW/f"{sid}.bin"),"-w","%{http_code} %{content_type} %{url_effective}",url],capture_output=True,text=True)
    code, ctype, eff = (r.stdout.split(" ",2)+["",""])[:3]
    if not (RAW/f"{sid}.bin").exists():
        (RAW/f"{sid}.bin").write_bytes(b""); code = code or "CURL_FAIL"; ctype = ctype or "none"
        print("CURL_STDERR:", r.stderr.strip()[:200])
    data = (RAW/f"{sid}.bin").read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    status = "OK"
    if code != "200": status = f"HTTP_{code}"
    if "pdf" in ctype.lower():
        (RAW/f"{sid}.pdf").write_bytes(data); (RAW/f"{sid}.bin").unlink()
        try:
            import fitz
            doc = fitz.open(RAW/f"{sid}.pdf"); txt="\n".join(p.get_text() for p in doc)
        except Exception as e: txt=f"PDF_EXTRACT_FAIL {e}"
        local=f"{sid}.pdf"
    else:
        (RAW/f"{sid}.html").write_bytes(data); (RAW/f"{sid}.bin").unlink()
        p=Text(); p.feed(data.decode("utf-8","replace")); txt=p.text(); local=f"{sid}.html"
        low=txt.lower()[:3000]
        if code=="200" and (len(txt)<800 or "captcha" in low or "access denied" in low or "enable javascript" in low):
            status="BLOCKED_OR_EMPTY"
    (RAW/f"{sid}.txt").write_text(txt)
    rec=dict(source_id=sid,url=url,url_effective=eff,http=code,content_type=ctype,status=status,local_file=local,sha256=sha,bytes=len(data),text_chars=len(txt),access_time=ts)
    with open(RAW/"fetch_log.jsonl","a") as f: f.write(json.dumps(rec)+"\n")
    print(json.dumps(rec))

if __name__=="__main__": main(sys.argv[1], sys.argv[2])
