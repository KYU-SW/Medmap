# 질의를 층위로 나눠 방법별 집계: T=시간·승인·정정 모델, X=문장 해석(추출), I=환자 식별, O=기타 대조
import csv, sys
LAYER = {}
for q in ["N01.q1","N01.q2","N02.q1","N02.q2","N03.q1","N03.q2","N06.q1","N06.q2","N07.q1","N08.q1","N08.q2","N13.q1","N13.q2","N13.q3","N14.q1","N14.q2","N15.q1","N15.q2","N11.q6"]: LAYER[q]="T"
for q in ["N04.q1","N04.q2","N05.q1","N05.q2","N09.q1","N09.q2","N09.q3","N10.q1","N10.q2","N10.q3","N10.q4","N10.q5","N11.q1","N11.q2","N11.q3","N11.q4","N11.q5","N12.q2","N16.q1","N16.q2"]: LAYER[q]="X"
LAYER["N12.q1"]="I"
out=[]
for suffix in ["", "_validtime_lexicon"]:
    rows=list(csv.DictReader(open(f"results_queries{suffix}.csv")))
    assert all(r["qid"] in LAYER for r in rows), [r["qid"] for r in rows if r["qid"] not in LAYER]
    agg={}
    for r in rows:
        k=(LAYER[r["qid"]], r["method"]); g=agg.setdefault(k,[0,0,0,0]); g[0]+=1; g[1]+=r["exact"]=="true"; g[2]+=r["acceptable"]=="true"; g[3]+=r["dangerous"]=="true"
    for (layer,m),g in sorted(agg.items()): out.append({"variant": suffix or "_extracted", "layer":layer,"method":m,"n":g[0],"exact":g[1],"acceptable":g[2],"dangerous":g[3]})
w=csv.DictWriter(open("results_by_layer.csv","w",newline=""), fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for o in out: print(o)
