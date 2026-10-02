#!/bin/bash
# OptimusKG (MIT, Harvard Dataverse doi:10.7910/DVN/IYNGEV) 전체 41파일 다운로드
# python-requests UA는 403 → curl + 브라우저 UA. 클라이언트 캐시 레이아웃(nodes/, edges/)과 동일하게 저장
set -u
D=~/medmap/data/optimuskg/gold; mkdir -p $D/nodes $D/edges
echo "START $(date)"
python3 -c "
import json;d=json.load(open('$HOME/medmap/data/optimuskg/dataverse_metadata.json'))
for f in d['data']['latestVersion']['files']:
    df=f['dataFile']; print(df['id'], (f.get('directoryLabel','')+'/'+df['filename']).lstrip('/'), df['filesize'])" | while read id rel size; do
  out=$D/$rel
  if [ -f "$out" ] && [ "$(stat -c %s "$out")" = "$size" ]; then echo "skip $rel"; continue; fi
  for t in 1 2 3 4 5; do
    curl -s -L -A "Mozilla/5.0" -o "$out" "https://dataverse.harvard.edu/api/access/datafile/$id" && [ "$(stat -c %s "$out")" = "$size" ] && { echo "ok $rel $size"; break; }
    echo "retry $t $rel"; sleep 5
  done
done
echo "DONE $(date)"
