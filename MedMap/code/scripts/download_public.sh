#!/bin/bash
# MedMap 공개 데이터 다운로드 (DDXPlus fr/en, HPO). 전부 무료·공개.
set -euo pipefail
# 기본 저장 위치 = 이 저장소의 code/data (엔진은 code/data/ddxplus/en/release_evidences.json 을 읽는다). MEDMAP_DATA_DIR 로 바꿀 수 있다.
D="${MEDMAP_DATA_DIR:-$(cd "$(dirname "$0")/.." && pwd)/data}"
mkdir -p "$D/ddxplus/fr" "$D/ddxplus/en" "$D/hpo"
W="wget -c --tries=20 --timeout=60 -q --show-progress"
echo "START $(date)"
# DDXPlus 원본(fr) figshare 20043374
cd "$D"/ddxplus/fr
$W -O README.md https://ndownloader.figshare.com/files/40495496
$W -O release_evidences.json https://ndownloader.figshare.com/files/40495562
$W -O release_conditions.json https://ndownloader.figshare.com/files/62657140
$W -O release_test_patients.zip https://ndownloader.figshare.com/files/40495565
$W -O release_validate_patients.zip https://ndownloader.figshare.com/files/40495571
$W -O release_train_patients.zip https://ndownloader.figshare.com/files/40495568
# DDXPlus English figshare 22687585
cd "$D"/ddxplus/en
$W -O release_evidences.json https://ndownloader.figshare.com/files/40278013
$W -O release_conditions.json https://ndownloader.figshare.com/files/62561569
$W -O release_test_patients.zip https://ndownloader.figshare.com/files/40278016
$W -O release_validate_patients.zip https://ndownloader.figshare.com/files/40278022
$W -O release_train_patients.zip https://ndownloader.figshare.com/files/40278019
# HPO 최신 release
cd "$D"/hpo
B=https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download
for f in hp.obo hp.json phenotype.hpoa genes_to_phenotype.txt phenotype_to_genes.txt; do $W -O $f $B/$f; done
# zip 해제 (unzip 바이너리 없음 → python zipfile)
for v in fr en; do cd "$D"/ddxplus/$v; for z in *.zip; do python3 -c "import zipfile,sys;zipfile.ZipFile('$z').extractall('.')" && echo "extracted $v/$z"; done; done
echo "DONE $(date)"
