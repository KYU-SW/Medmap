"""NCBI E-utilities fetch (public API, no key; <=3 req/s). Saves XML + text + sha256.
Usage: python s15v2_efetch.py <source_id> <db: pubmed|pmc> <id>"""
import sys, hashlib, json, datetime, pathlib, subprocess, re, time
RAW = pathlib.Path("data/disease_profiles_v2/raw")
def main(sid, db, ident):
    url=f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db={db}&id={ident}&retmode=xml"
    ts=datetime.datetime.now().isoformat(timespec="seconds")
    r=subprocess.run(["curl","-sS","--max-time","60","-o",str(RAW/f"{sid}.xml"),"-w","%{http_code}",url],capture_output=True,text=True)
    data=(RAW/f"{sid}.xml").read_bytes(); sha=hashlib.sha256(data).hexdigest()
    x=data.decode("utf-8","replace")
    txt=re.sub(r"<[^>]+>"," ",x); txt=re.sub(r"[ \t]+"," ",txt); txt=re.sub(r"\n\s*\n+","\n",txt).strip()
    (RAW/f"{sid}.txt").write_text(txt)
    status="OK" if r.stdout=="200" and len(txt)>500 and "error" not in x[:300].lower() else f"HTTP_{r.stdout}_chars{len(txt)}"
    rec=dict(source_id=sid,url=url,http=r.stdout,status=status,local_file=f"{sid}.xml",sha256=sha,bytes=len(data),text_chars=len(txt),access_time=ts,fetch_method="ncbi_eutils")
    with open(RAW/"fetch_log.jsonl","a") as f: f.write(json.dumps(rec)+"\n")
    print(json.dumps(rec)); time.sleep(0.4)
if __name__=="__main__": main(*sys.argv[1:4])
