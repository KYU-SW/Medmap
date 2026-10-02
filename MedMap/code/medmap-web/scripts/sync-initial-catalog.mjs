// initial 96개 표시 라벨을 Python 정본(medmap/data/initial_evidence_ko.json)에서 프론트로 복사한다.
// 폴더는 src/intake/ — 루트 .gitignore 의 data/ 규칙을 피한다(src/data 는 커밋되지 않는다).
import { copyFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
copyFileSync(resolve(here, '../../medmap/data/initial_evidence_ko.json'), resolve(here, '../src/intake/initialCatalog.json'))
console.log('synced src/intake/initialCatalog.json')
