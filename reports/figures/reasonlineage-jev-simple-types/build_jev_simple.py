"""Keep the approved lineage and replace the detailed jev footer with three steps."""
import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'pyproject.toml').is_file())
sys.path.insert(0, str(ROOT / '.superpowers/figure-animation-deps'))
import cairosvg
import imageio_ffmpeg
from PIL import Image

spec = importlib.util.spec_from_file_location('scored', ROOT / '.superpowers/figure-animation/build_scored_lineage.py')
scored = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scored)
base = scored.base
base.H = 900
W, H, FPS, LENGTH = 1664, 900, 15, 28
OUT = ROOT / 'reports/figures/reasonlineage-jev-simple'
STEPS = [('Check response', 'Required parts'),
         ('Revise if needed', 'Same author · once'),
         ('Recheck & record', 'Keep remaining flags')]
CHAPTERS = list(base.CHAPTERS)
CHAPTERS[1] = (3, 'jev · check → optional revision → recheck', 'jev가 답변을 점검합니다. 확인된 결함이 있으면 같은 작성자가 한 번 보완하고 재확인합니다. 이 첫 장면은 보완 경로의 예시입니다.')
CHAPTERS[2] = (4, 'Three non-author reviewers', '작성자를 제외한 세 모델이 답변을 평가합니다. 예시 fitness는 채점 후 표시됩니다.')
for index, time in [(6, 9), (11, 15), (16, 21)]:
    CHAPTERS[index] = (time, 'jev · no gap → peer scoring', '새 답변을 점검합니다. 확인된 결함이 없는 이 장면에서는 보완 없이 LLM 평가로 넘어갑니다. 미해결 사항은 기록합니다.')


def footer(t, static=False):
    pulse = next((i for i, c in enumerate(base.CHECK) if c <= t < c + .85), None)
    active = None
    direct = False
    if not static and pulse is not None:
        elapsed = t - base.CHECK[pulse]
        if pulse == 0:
            active = 0 if elapsed < .27 else 1 if elapsed < .56 else 2
        else:
            active = 0
            direct = elapsed >= .35
    p = [base.box(24, 704, 1616, 133, '#f8fcfa', '#dbe8e0')]
    p += [base.txt(58, 776, 'jev', 28, '#3b745a', 700),
          base.txt(58, 801, 'New responses', 13, '#728d7c')]
    # A single bypass makes the revision conditional, rather than mandatory.
    route_color = '#4b9973' if direct else '#b2c4ba'
    p.append(f'<path id="jev-pass" d="M402,752 V732 H1466 V754" fill="none" stroke="{route_color}" stroke-width="1.4" marker-end="url(#jev-arrow)"/>')
    p.append(base.txt(933, 724, 'No confirmed gap → peer scoring', 12, '#61816e', 500, 'middle'))
    for index, ((title, subtitle), x) in enumerate(zip(STEPS, [252, 620, 988])):
        on = active == index
        p.append(f'<g id="jev-step-{index + 1}" data-active="{str(on).lower()}">')
        p.append(base.box(x, 753, 300, 64, '#def2e6' if on else '#ffffff', '#64a780' if on else '#c8dbcf'))
        p.append(f'<circle cx="{x+24}" cy="779" r="12" fill="{"#4b8e67" if on else "#e6f0ea"}"/>')
        p.append(base.txt(x+24, 783, index+1, 12, '#ffffff' if on else '#58806a', 700, 'middle'))
        p.append(base.txt(x+47, 782, title, 16, '#355c45', 700))
        p.append(base.txt(x+47, 805, subtitle, 12.5, '#799080'))
        p.append('</g>')
    for start, end in [(563, 606), (931, 974), (1300, 1380)]:
        p.append(f'<path d="M{start},783 H{end}" stroke="#94b09f" stroke-width="1.8" fill="none" marker-end="url(#jev-arrow)"/>')
    p.append(base.txt(1466, 780, 'LLM peer', 14, '#597284', 600, 'middle'))
    p.append(base.txt(1466, 803, 'scoring', 14, '#597284', 600, 'middle'))
    return ''.join(p)


def svg(t=27, static=False):
    s = scored.svg(t, static)
    s = s.replace('height="840" viewBox="0 0 1664 840"', 'height="900" viewBox="0 0 1664 900"')
    s = s.replace('</defs><g font-family=', '<marker id="jev-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="#94b09f"/></marker></defs><g font-family=', 1)
    old = (base.box(737,717,410,61,'#dcf5e9' if any(c<=t<c+.85 for c in base.CHECK) and not static else '#f2faf6','#b8d6c6')
           + base.txt(768,745,'jev',21,'#3b745a',700)
           + base.txt(827,740,'Check new responses',14,'#557564')
           + base.txt(827,762,'Separate from fitness scoring',11,'#789283'))
    assert s.count(old) == 1
    s = s.replace(old, footer(t, static))
    s = s.replace('H942 V716', 'H942 V703')
    # Preserve the existing legend and explicit illustrative-score disclaimer.
    for x, label in [(114, 'Retain'), (417, 'Mutation'), (762, 'Crossover')]:
        s = s.replace(f'd="M{x},802 h56"', f'd="M{x},861 h56"')
        s = s.replace(base.txt(x+66,807,label,14,'#627482'), base.txt(x+66,866,label,14,'#627482'))
    s = s.replace(base.txt(1093,807,'LLM critics → fitness → selection',13,'#73818b'),
                  base.txt(1093,866,'LLM critics → fitness → selection',13,'#73818b'))
    note = 'Illustrative fitness values (0–1) · not empirical model scores or correctness probabilities'
    assert s.count(base.txt(base.W/2,829,note,11,'#95a1aa',anchor='middle')) == 1
    s = s.replace(base.txt(base.W/2,829,note,11,'#95a1aa',anchor='middle'),
                  base.txt(base.W/2,891,note,11,'#95a1aa',anchor='middle'))
    return s


def main():
    assert not OUT.exists(), 'New output directory required; preserve previous figures.'
    OUT.mkdir(parents=True)
    static = svg(static=True)
    (OUT/'overview.svg').write_text(static)
    image = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=static.encode(), output_width=W*2, output_height=H*2)))
    image.save(OUT/'overview-native.png', dpi=(300,300))
    spec = importlib.util.spec_from_file_location('player', ROOT/'.superpowers/figure-animation/build_animation.py')
    player = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(player)
    player.FPS, player.LENGTH, player.CHAPTERS = FPS, LENGTH, CHAPTERS
    frames = [svg(i/FPS) for i in range(FPS*LENGTH+1)]
    markup = player.html_player(frames).replace('max="25"', 'max="28"')
    markup = markup.replace('개념 애니메이션 · 4모델 구성', '개념 애니메이션 · 간단한 jev 점검 흐름')
    markup = markup.replace('색상과 선택 결과는 원리를 설명하는 예시이며 실제 모델 순위를 뜻하지 않습니다.',
                             '점수는 설명용 예시입니다. jev는 구조를 점검하고, fitness는 작성자를 제외한 LLM이 계산합니다.')
    (OUT/'animation.html').write_text(markup)
    metadata = {'kind':'illustrative_lineage_simple_jev', 'empirical_scores':False,
                'models':base.PROVIDERS, 'reviewers':scored.REVIEWERS,
                'fitness_scorer':'non-author LLM critics', 'jev_role':'structural feedback',
                'steps':STEPS, 'revision_limit':1, 'same_author_revision':True,
                'complete_responses_skip_revision':True, 'unresolved_flags_recorded':True,
                'first_inspection_animation':'illustrative revision path',
                'later_inspection_animation':'illustrative direct pass path',
                'illustrative_fitness':scored.SCORES, 'nodes':base.NODES,
                'populations':base.POPS, 'selected':base.SELECTED,
                'chapters':CHAPTERS, 'width':W, 'height':H, 'fps':FPS, 'duration':LENGTH}
    (OUT/'lineage.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    writer = imageio_ffmpeg.write_frames(str(OUT/'animation.mp4'), (W,H), fps=FPS, codec='libx264',
        pix_fmt_out='yuv420p', macro_block_size=1, quality=8,
        output_params=['-movflags','+faststart'], ffmpeg_log_level='error')
    writer.send(None)
    gif = []
    for i, frame in enumerate(frames[:-1]):
        picture = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=frame.encode(), output_width=W, output_height=H))).convert('RGB')
        writer.send(picture.tobytes())
        gif.append(picture.resize((1248,675), Image.Resampling.LANCZOS).quantize(colors=96, method=Image.Quantize.FASTOCTREE))
        if i in [46, 50, 55, 142, 245, 419]:
            picture.save(OUT/f'frame-{i:03d}.png')
        if i % 90 == 0:
            print(json.dumps({'rendered':i,'total':420}), flush=True)
    writer.close()
    durations = [round((i+1)*100/FPS)*10-round(i*100/FPS)*10 for i in range(len(gif))]
    gif[0].save(OUT/'animation.gif', save_all=True, append_images=gif[1:], duration=durations, loop=0, optimize=False, disposal=2)
    for name in ['build_jev_simple.py','build_scored_lineage.py','build_lineage_overview.py','build_animation.py','verify_lineage_player.js']:
        (OUT/name).write_text((ROOT/'.superpowers/figure-animation'/name).read_text())
    print(json.dumps({'status':'rendered','output':str(OUT),'frames':len(frames),'duration':LENGTH}), flush=True)


if __name__ == '__main__':
    main()
