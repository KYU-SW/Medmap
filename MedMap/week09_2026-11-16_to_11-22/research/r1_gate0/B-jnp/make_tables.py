"""CSV -> 집계 CSV + 보고서용 markdown 표 (report_tables.md). 숫자는 모두 CSV 에서 계산."""
import glob
import os
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
FL = ['AA', 'EE', 'AE', 'EA', 'EwAs']
DEFINITE = {'ALWAYS', 'EXCLUDED'}


def load(pattern):
    fs = [f for f in sorted(glob.glob(os.path.join(D, pattern))) if not f.endswith('_time.csv')]
    return pd.concat([pd.read_csv(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def compare(df):
    key = ['sweep', 'param', 'value', 'seed', 'option']
    tr = df[df.method == 'exact_enum'][key + FL + ['cat']].rename(columns={c: 't_' + c for c in FL + ['cat']})
    m = df[df.method != 'exact_enum'].merge(tr, on=key, how='inner')
    for c in FL:
        valid = m['t_' + c].notna() & m[c].notna()
        m[c + '_ok'] = (m[c] == m['t_' + c]).where(valid)
    m['flags4_ok'] = m[[c + '_ok' for c in FL[:4]]].all(axis=1)
    m['cat_ok'] = m['cat'] == m['t_cat']
    m['wrong_confirm'] = m['cat'].isin(DEFINITE) & (m['cat'] != m['t_cat'])
    m['unneeded_hold'] = m['t_cat'].isin(DEFINITE) & ~m['cat'].isin(DEFINITE)
    m['false_AA'] = (m['AA'] == 1) & (m['t_AA'] == 0)
    m['false_EwAs'] = (m['EwAs'] == 1) & (m['t_EwAs'] == 0)
    return m


def md(df, floatfmt=3):
    cols = list(df.columns)
    out = ['| ' + ' | '.join(map(str, cols)) + ' |', '|' + '---|' * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(f"{v:.{floatfmt}f}" if isinstance(v, float) else str(v))
        out.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(out)


def main():
    df = load('results_main_*.csv')
    m = compare(df)
    lines = []
    n_inst = df[df.method == 'exact_enum'][['sweep', 'value', 'seed']].drop_duplicates().shape[0]
    n_opt = df[df.method == 'exact_enum'].shape[0]
    lines.append(f"총 인스턴스 {n_inst}개, 선택지 판정 {n_opt}개 (exact_enum 기준).\n")
    # overall
    g = m.groupby('method').agg(n=('cat_ok', 'size'), cat_match=('cat_ok', 'mean'), flags4_match=('flags4_ok', 'mean'),
                                AA_match=('AA_ok', 'mean'), EE_match=('EE_ok', 'mean'), AE_match=('AE_ok', 'mean'),
                                EA_match=('EA_ok', 'mean'), EwAs_match=('EwAs_ok', 'mean'),
                                wrong_confirm=('wrong_confirm', 'sum'), unneeded_hold=('unneeded_hold', 'sum'),
                                false_AA=('false_AA', 'sum'), false_EwAs=('false_EwAs', 'sum')).reset_index()
    order = ['milp', 'jnp_candidate', 'ror_lp_combo', 'ror_pw_combo', 'vertex_only', 'penalty_P10', 'penalty_P1',
             'closed_world', 'ignore_unknown']
    g['o'] = g.method.map({k: i for i, k in enumerate(order)}); g = g.sort_values('o').drop(columns='o')
    g.to_csv(os.path.join(D, 'results_summary_overall.csv'), index=False)
    lines.append("### 표 1. 전체 정답 일치 (exact_enum 대비)\n")
    lines.append(md(g))
    # truth category distribution
    tc = df[df.method == 'exact_enum'].cat.value_counts().rename_axis('cat').reset_index(name='count')
    lines.append("\n### 표 2. 정답 범주 분포\n")
    lines.append(md(tc))
    # EwAs undefined in exact
    nn = df[(df.method == 'exact_enum') & df.EwAs.isna()].shape[0]
    lines.append(f"\nexact_enum 에서 EwAs 를 조합 한도 때문에 계산하지 못한 선택지: {nn}개 (해당 행은 EwAs 비교에서 제외).\n")
    # per sweep for naive methods
    lines.append("### 표 3. 조건별 범주 일치율 (sweep 값별)\n")
    piv = m.groupby(['sweep', 'value', 'method']).cat_ok.mean().unstack('method')
    piv = piv[[c for c in order if c in piv.columns]].reset_index()
    piv.to_csv(os.path.join(D, 'results_summary_by_sweep.csv'), index=False)
    lines.append(md(piv))
    lines.append("\n### 표 4. 조건별 잘못된 확정 수 / 불필요 보류 수 (sweep 값별, 비정확 기준선)\n")
    w = m.groupby(['sweep', 'value', 'method']).agg(wc=('wrong_confirm', 'sum'), uh=('unneeded_hold', 'sum'))
    w['wc/uh'] = w.wc.astype(int).astype(str) + '/' + w.uh.astype(int).astype(str)
    w = w['wc/uh'].unstack('method')
    cols = [c for c in ['ror_pw_combo', 'vertex_only', 'penalty_P1', 'closed_world', 'ignore_unknown'] if c in w.columns]
    lines.append(md(w[cols].reset_index()))
    # timing
    tdf = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(D, 'results_main_*_time.csv')))])
    errs = tdf[tdf.error.notna()]
    lines.append(f"\n실행 오류 행 수: {len(errs)}\n")
    tt = tdf.groupby('method').time_s.agg(['count', 'median', 'mean', 'max']).reset_index()
    tt.to_csv(os.path.join(D, 'results_summary_time.csv'), index=False)
    lines.append("### 표 5. 인스턴스당 계산 시간 (초, 전체 main sweep)\n")
    lines.append(md(tt, 4))
    tn = tdf[tdf.sweep == 'nU'].groupby(['value', 'method']).time_s.median().unstack('method').reset_index()
    lines.append("\n### 표 6. 미확인 조건 수별 중앙 시간 (초)\n")
    lines.append(md(tn, 4))
    sig = tdf[(tdf.sweep == 'nU') & (tdf.method.isin(['jnp_candidate', 'exact_enum']))]
    sg = sig.groupby(['value', 'method'])[['n_worlds', 'n_signatures']].median().unstack('method').reset_index()
    sg.columns = ['_'.join(map(str, c)).strip('_') for c in sg.columns]
    sg = sg[[c for c in sg.columns if not c.endswith('nan') and sg[c].notna().any()]]
    lines.append("\n### 표 7. 미확인 조건 수별 중앙 상태 수(exact) vs 서명 수(candidate)\n")
    lines.append(md(sg, 1))
    # scaling
    sf = os.path.join(D, 'results_scaling_time.csv')
    if os.path.exists(sf):
        s = pd.read_csv(sf)
        ss = s.groupby(['value', 'method']).agg(time_med=('time_s', 'median'), peak_mb_med=('peak_mem_mb', 'median'),
                                                n=('time_s', 'size')).reset_index()
        ss.to_csv(os.path.join(D, 'results_summary_scaling.csv'), index=False)
        lines.append("\n### 표 8. 확장성 (nU 4~20, 인스턴스 3개/점, 중앙값; exact·ror_lp_combo 는 nU<=14 만)\n")
        lines.append(md(ss, 4))
        so = load('results_scaling.csv')
        if len(so):
            sm = compare(so)
            sa = sm.groupby(['value', 'method']).cat_ok.mean().unstack('method').reset_index()
            lines.append("\n### 표 9. 확장성 실험의 범주 일치율 (exact 가 있는 nU 만)\n")
            lines.append(md(sa))
            # milp vs candidate agreement at all nU
            mc = so[so.method.isin(['milp', 'jnp_candidate'])].pivot_table(
                index=['value', 'seed', 'option'], columns='method', values='cat', aggfunc='first').reset_index()
            mc['agree'] = mc['milp'] == mc['jnp_candidate']
            lines.append("\n### 표 10. MILP vs candidate 범주 일치율 (nU 전 구간)\n")
            lines.append(md(mc.groupby('value').agree.mean().reset_index()))
    stf = os.path.join(D, 'results_stress_time.csv')
    if os.path.exists(stf):
        s = pd.read_csv(stf)
        ss = s.groupby(['value', 'method']).agg(time_med=('time_s', 'median'), time_max=('time_s', 'max'),
                                                peak_mb_med=('peak_mem_mb', 'median'),
                                                sig_med=('n_signatures', 'median'), n=('time_s', 'size')).reset_index()
        ss.to_csv(os.path.join(D, 'results_summary_stress.csv'), index=False)
        lines.append("\n### 표 11. 스트레스 확장성 (금기 규칙 수 = nU, 상태의존 점수 수 = nU//2; 3개/점; exact·ror_lp_combo 는 nU<=14)\n")
        lines.append(md(ss, 4))
        so = load('results_stress.csv')
        sm = compare(so)
        lines.append("\n### 표 12. 스트레스 실험 범주 일치율 (exact 있는 nU) 및 MILP–candidate 일치율 (전 구간)\n")
        lines.append(md(sm.groupby(['value', 'method']).cat_ok.mean().unstack('method').reset_index()))
        mc = so[so.method.isin(['milp', 'jnp_candidate'])].pivot_table(
            index=['value', 'seed', 'option'], columns='method', values='cat', aggfunc='first').reset_index()
        mc['agree'] = mc['milp'] == mc['jnp_candidate']
        lines.append('')
        lines.append(md(mc.groupby('value').agree.mean().reset_index()))
    open(os.path.join(D, 'report_tables.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
