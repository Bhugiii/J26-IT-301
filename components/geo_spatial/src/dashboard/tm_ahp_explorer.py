"""TravelMind: tourist-friendly observed resource explorer + opt-in research AHP demo.
No official TPI is generated. Uses only already processed Sri Lanka 5 km grid features.
Place beside src/dashboard/app.py as src/dashboard/tm_ahp_explorer.py.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
GRID_PATH = ROOT / 'data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv'
FEATURES = {
    'Places to explore': 'attraction_count',
    'Places to stay': 'service_group_accommodation_count',
    'Places to eat': 'service_group_food_and_drink_count',
    'Travel services': 'service_group_travel_support_count',
}
RI_FOUR = 0.90

@st.cache_data(show_spinner=False)
def _load_grid():
    d = pd.read_csv(GRID_PATH, low_memory=False)
    required = {'grid_id', 'center_latitude', 'center_longitude', 'boundary_overlap_fraction', *FEATURES.values()}
    missing = required - set(d.columns)
    if missing:
        raise ValueError(f'Grid missing required columns: {sorted(missing)}')
    for c in ['center_latitude', 'center_longitude', 'boundary_overlap_fraction', *FEATURES.values()]:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['center_latitude', 'center_longitude', 'boundary_overlap_fraction', *FEATURES.values()])
    d = d[d.boundary_overlap_fraction >= 0.5].copy()
    # No POI records is not evidence of an absence of tourism; keep zeros in data,
    # but exclude them from highlighted/searchable 'mapped resources' subset.
    for c in FEATURES.values():
        d[c] = d[c].clip(lower=0)
    d['total_mapped'] = d[list(FEATURES.values())].sum(axis=1)
    return d

def _ahp_matrix(pairwise):
    n = 4
    m = np.ones((n,n), dtype=float)
    for (i,j), v in pairwise.items():
        ratio = float(v + 1) if v >= 0 else 1.0 / float(1 - v)
        m[i,j],m[j,i] = ratio, 1.0 / ratio
    eigenvalues,eigenvectors=np.linalg.eig(m)
    idx=int(np.argmax(eigenvalues.real))
    vec=np.abs(eigenvectors[:,idx].real)
    weights=vec/vec.sum()
    lam=float(eigenvalues[idx].real)
    ci=max(0.0,(lam - n)/(n-1))
    return weights, ci/RI_FOUR

def _scores(frame, weights):
    # Explicit heuristic: log compression and fixed within-sample 95th percentile.
    # Results depend on mapping coverage and the selected sample.
    x=[]
    for name,col in FEATURES.items():
        v=np.log1p(frame[col].to_numpy(dtype=float))
        cap=float(np.percentile(v,95))
        x.append(np.clip(v / cap, 0, 1) if cap > 0 else np.zeros_like(v))
    return np.vstack(x).T @ weights

def render_tourism_potential():
    st.markdown('### 🌿 Explore tourism resources')
    st.caption('Explore mapped attractions and nearby services across Sri Lanka. This helps compare what is mapped, not how enjoyable, safe or popular a place is.')
    if not GRID_PATH.is_file():
        st.warning('The tourism-resource map is not ready yet. Its supporting local dataset could not be found.')
        return
    try:
        grid = _load_grid()
    except Exception as exc:
        st.error(f'Unable to prepare resource explorer: {exc}')
        return
    available=grid[grid.total_mapped > 0].copy()
    if available.empty:
        st.info('No mapped facilities or attractions are available for this explorer.')
        return

    left,right=st.columns([2,1])
    with left:
        interest=st.selectbox('What would you like to find?', list(FEATURES), index=0, key='tpi_interest')
    with right:
        minimum=st.select_slider('Minimum mapped places of that type', options=[1,2,5,10,20], value=2, key='tpi_minimum')
    choice_col=FEATURES[interest]
    matches=available[available[choice_col]>=minimum].sort_values(choice_col, ascending=False)
    st.caption('Map points represent the centres of approximately 5 km grid cells, not exact attraction or hotel locations.')
    if matches.empty:
        st.info('No map areas match this filter. Try lowering the minimum.')
    else:
        st.map(matches.head(300).rename(columns={'center_latitude':'latitude','center_longitude':'longitude'}),latitude='latitude',longitude='longitude',size=65,zoom=7)
        st.markdown('**Explore a mapped area**')
        choices=matches.head(200).copy()
        names={str(r.grid_id):f'Area near {r.center_latitude:.3f}°N, {r.center_longitude:.3f}°E' for r in choices.itertuples()}
        gid=st.selectbox('Choose an area on the list',list(names),format_func=lambda k:names[k],key='tpi_area_choice')
        r=choices.loc[choices.grid_id.astype(str).eq(gid)].iloc[0]
        cols=st.columns(4)
        for panel,(label,column) in zip(cols,FEATURES.items()):
            panel.metric(label,int(r[column]))
        st.caption('Counts describe mapped candidate records in the surrounding grid cell. They do not indicate available bookings, attraction quality or verified services.')

    st.divider()
    with st.expander('🔬 AHP research workshop — compare what matters (experimental)', expanded=False):
        st.markdown('#### Step 1 · What are we assessing?')
        st.write(
            'This first experiment compares **mapped tourist resources** in 5 km areas. '
            'It is **not** a validated index of destination quality, visitor enjoyment, safety, '
            'accessibility, or development potential.'
        )
        st.caption(
            'AHP weights express research judgments, not facts derived from the point counts. '
            'For a publishable TPI, record who provided judgments, why, and when.'
        )
        researcher = st.text_input('Judgment source / assessor', placeholder='Research team, expert panel, etc.', key='ahp_reviewer')
        purpose = st.text_area(
            'Why are these criteria and comparisons appropriate?',
            placeholder='Explain the intended objective, why each criterion was included, and whose priorities these represent.',
            key='ahp_purpose', height=92
        )
        st.markdown('#### Step 2 · Compare factors in pairs')
        st.caption('For each pair, choose which matters more, then how strongly. Equal means both factors matter equally.')
        labels = list(FEATURES)
        pairs = {}
        audit_rows = []
        for i in range(len(labels)):
            for j in range(i+1, len(labels)):
                a, b = labels[i], labels[j]
                with st.container(border=True):
                    st.markdown(f'**{a}** compared with **{b}**')
                    winner = st.radio(
                        f'Which is more important for this research objective? ({a} / {b})',
                        ['Equally important', a, b], horizontal=True,
                        key=f'ahp_winner_{i}_{j}',
                    )
                    strength = 1
                    if winner != 'Equally important':
                        strength = st.select_slider(
                            'How much more important?', options=[2,3,4,5,6,7,8,9], value=3,
                            help='Saaty scale: 3 = moderate, 5 = strong, 7 = very strong, 9 = extreme. Even numbers are intermediate judgments.',
                            key=f'ahp_strength_{i}_{j}',
                        )
                    rationale = st.text_input(
                        'Reason or supporting reference (recommended)',
                        placeholder='Why should this factor receive more weight?',
                        key=f'ahp_reason_{i}_{j}',
                    )
                ratio = 1.0 if winner == 'Equally important' else (float(strength) if winner == a else 1/float(strength))
                # _ahp_matrix uses a signed 0..8 offset for Saaty 1..9.
                signed = 0 if winner == 'Equally important' else ((strength-1) if winner == a else -(strength-1))
                pairs[(i,j)] = signed
                audit_rows.append({
                    'criterion_a':a, 'criterion_b':b, 'preferred':winner,
                    'saaty_ratio_a_to_b':ratio, 'strength':strength,
                    'reason':rationale.strip(),
                })
        weights, cr = _ahp_matrix(pairs)
        st.markdown('#### Step 3 · See the AHP weights and consistency')
        weight_table = pd.DataFrame({'Factor':labels, 'Weight':weights, 'Weight (%)':weights*100})
        st.dataframe(weight_table.style.format({'Weight':'{:.4f}','Weight (%)':'{:.1f}%'}), hide_index=True, use_container_width=True)
        st.bar_chart(weight_table.set_index('Factor')['Weight (%)'])
        st.metric('AHP consistency ratio (CR)', f'{cr:.3f}')
        acceptable = bool(np.isfinite(cr) and cr < 0.10)
        if not acceptable:
            st.warning('CR is 0.10 or higher. Some preferences conflict; revise the six comparisons before interpreting weighted results.')
        else:
            st.success('CR is below 0.10: the six judgments are internally consistent under the AHP test. This does not validate the data or the criteria.')
        st.markdown('#### Step 4 · Save the research record')
        from datetime import datetime, timezone
        import json
        record = {
            'module':'TravelMind experimental AHP resource comparison',
            'assessment_objective':'Relative concentration of mapped tourist resources in 5 km Sri Lanka grid cells',
            'assessor':researcher.strip(),
            'justification':purpose.strip(),
            'criteria':labels,
            'comparisons':audit_rows,
            'weights':{label:float(w) for label,w in zip(labels,weights)},
            'consistency_ratio':float(cr),
            'passes_cr_check':acceptable,
            'data_source':'data/processed/tourism_infrastructure/tourism_infrastructure_grid_5km.csv',
            'limitations':[
                'Overture and OSM-derived POIs are not independently verified',
                'Road accessibility and geographic constraints have not been included',
                'Coastal grid cells below 50% boundary overlap are excluded',
                'Weights are unvalidated user judgments, not expert consensus',
                'Comparisons depend on mapping coverage and normalization',
            ],
        }
        st.download_button('Download AHP judgment record (JSON)',
            data=json.dumps(record,ensure_ascii=False,indent=2),
            file_name='travelmind_ahp_judgments_experimental.json',mime='application/json',
            key='ahp_download_research')
        if not researcher.strip() or not purpose.strip() or any(not row['reason'] for row in audit_rows):
            st.caption('For a research report, complete assessor, purpose, and comparison reasons before using this exported record as evidence.')
        st.markdown('#### Step 5 · Optional exploratory comparison')
        show = st.checkbox('Show experimental resource comparison (research only)', value=False, key='ahp_experiment_visible')
        if show:
            if not acceptable:
                st.info('Improve consistency before calculating a combined experimental comparison.')
            else:
                trial=available.copy()
                trial['experimental_resource_index']=_scores(trial,weights)
                trial=trial.sort_values('experimental_resource_index',ascending=False)
                display=trial.head(20)[['grid_id','experimental_resource_index',*FEATURES.values()]]
                st.dataframe(display.rename(columns={'grid_id':'Grid cell', **{v:k for k,v in FEATURES.items()}}).round(3),hide_index=True,use_container_width=True)
                st.caption('These are experimental normalized resource scores, not a tourism-potential ranking, travel recommendation, or official TPI.')
                # Sensitivity screen: independent 10% adjustments to each AHP weight.
                baseline=set(trial.head(20).grid_id.astype(str))
                changes=[]
                for idx,name in enumerate(labels):
                    for multiplier in (0.9,1.1):
                        varied=weights.copy()
                        varied[idx]*=multiplier
                        varied=varied/varied.sum()
                        check=available.copy()
                        check['score']=_scores(check,varied)
                        top=set(check.nlargest(20,'score').grid_id.astype(str))
                        changes.append({'Adjusted factor':name,'Weight adjustment':f'{multiplier:.0%}',
                                        'Top-20 grid cells retained':len(baseline & top)})
                with st.expander('Sensitivity: what if a weight changes by 10%?'):
                    st.dataframe(pd.DataFrame(changes),hide_index=True,use_container_width=True)
                    st.caption('Simple weight-perturbation diagnostic, not full model validation. The baseline and alternatives use the same data and normalization.')
        st.info(
            'Before publishing a final tourist-facing TPI: agree a precise purpose, obtain and document defensible AHP judgments, '
            'add independent accessibility and constraint evidence, validate locations, and check spatial and weighting sensitivity.'
        )
