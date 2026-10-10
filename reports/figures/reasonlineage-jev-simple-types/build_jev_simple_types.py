"""Add three short typed-check labels inside the existing compact jev check step."""
import importlib.util
import json
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
spec = importlib.util.spec_from_file_location('simple', ROOT/'.superpowers/figure-animation/build_jev_simple.py')
simple = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simple)
base = simple.base
simple.OUT = ROOT/'reports/figures/reasonlineage-jev-simple-types'
TYPES = [('Noul', 'Present?'), ('Score', 'Adequate?'), ('Choice', 'Priority gap?')]
simple.STEPS[0] = ('Check response', 'Presence · Adequacy · Priority gap')
simple.CHAPTERS[1] = (3, 'jev · Noul / Score / Choice', 'jev가 Noul로 답변 존재, Score로 내용의 충분함, Choice로 우선 보완 항목을 점검합니다. 확인된 결함은 같은 작성자가 한 번 보완하고 재확인합니다. 이 장면은 설명용 보완 경로입니다.')


def footer(t, static=False):
    pulse = next((i for i, c in enumerate(base.CHECK) if c <= t < c+.85), None)
    active, direct = None, False
    if not static and pulse is not None:
        elapsed = t-base.CHECK[pulse]
        if pulse == 0:
            active = 0 if elapsed < .27 else 1 if elapsed < .56 else 2
        else:
            active, direct = 0, elapsed >= .35
    p = [base.box(24,704,1616,133,'#f8fcfa','#dbe8e0'),
         base.txt(58,776,'jev',28,'#3b745a',700),
         base.txt(58,801,'New responses',13,'#728d7c')]
    route_color = '#4b9973' if direct else '#b2c4ba'
    p.append(f'<path id="jev-pass" d="M484,752 V732 H1476 V754" fill="none" stroke="{route_color}" stroke-width="1.4" marker-end="url(#jev-arrow)"/>')
    p.append(base.txt(985,724,'No confirmed gap → peer scoring',12,'#61816e',500,'middle'))
    for index, ((title, subtitle), x, width) in enumerate(zip(simple.STEPS,[235,805,1115],[505,245,245])):
        on = active == index
        p.append(f'<g id="jev-step-{index+1}" data-active="{str(on).lower()}">')
        p.append(base.box(x,753,width,72,'#def2e6' if on else '#ffffff','#64a780' if on else '#c8dbcf'))
        p.append(f'<circle cx="{x+24}" cy="777" r="12" fill="{"#4b8e67" if on else "#e6f0ea"}"/>')
        p.append(base.txt(x+24,781,index+1,12,'#ffffff' if on else '#58806a',700,'middle'))
        p.append(base.txt(x+47,780,title,16,'#355c45',700))
        if index == 0:
            # The three types are parallel checks within one inspection, not three workflow stages.
            for (name, meaning), column in zip(TYPES,[x+47,x+197,x+337]):
                p.append(f'<g class="jev-type" data-type="{name}">')
                p.append(base.txt(column,800,name,12.5,'#51795f',700))
                p.append(base.txt(column,817,meaning,11.5,'#7c9183'))
                p.append('</g>')
        else:
            p.append(base.txt(x+47,807,subtitle,12,'#799080'))
        p.append('</g>')
    for start,end in [(749,789),(1059,1099),(1369,1418)]:
        p.append(f'<path d="M{start},785 H{end}" stroke="#94b09f" stroke-width="1.8" fill="none" marker-end="url(#jev-arrow)"/>')
    p += [base.txt(1476,780,'LLM peer',14,'#597284',600,'middle'),
          base.txt(1476,803,'scoring',14,'#597284',600,'middle')]
    return ''.join(p)


simple.footer = footer


def main():
    simple.main()
    path = simple.OUT/'lineage.json'
    data = json.loads(path.read_text())
    data['jev_types'] = dict(TYPES)
    data['type_composition'] = 'parallel assessments within Check response; not sequential Noul→Score→Choice stages'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    (simple.OUT/Path(__file__).name).write_text(Path(__file__).read_text())


if __name__ == '__main__':
    main()
