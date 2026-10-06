# 문헌 검증 — 2026-10-06 재시험

검증 범위는 주요 생물학적 전제, 선행 연구와 약물 승인 적응증이다. 모든 문장의 진실성·신규성을 포괄적으로 입증하거나 실제 실험을 수행한 것은 아니다. 확인 자료를 생성 모델이나 별도 LLM 평가자에게 추가 제공하지 않았다. 전문가에게는 정식 익명 평가를 마친 뒤 이 파일을 공개한다.

기존 여덟 입력 논문은 2026-10-05 메타데이터·요약을 확인한 자료를 그대로 사용했다. 이번 동결 파일의 해시가 원래 입력과 일치한다. 문헌을 2025년 이전으로 선택해도 모델의 사전 학습 지식까지 제한되지는 않는다.

## ALS: 확인된 전제와 질환 원인 가설

입력 S1–S4는 TDP-43·C9orf72·스트레스 과립과 핵 수송 이상 사이의 연결을 제공한다. 핵공 단백질의 특정 인산화가 ALS 운동뉴런의 시작 원인이라는 연결은 제공하지 않는다. 초기 다중 모델 가설 네 개는 모두 NUP98을 택했지만 GPT 단독 최종 답은 NUP62/p38α다. 모든 모델이 같은 표적만 택했다고 일반화하지 않는다.

[Laurell et al., Cell 2011](https://pubmed.ncbi.nlm.nih.gov/21335236/)은 CDK1·NEK 계열을 포함한 NUP98 인산화와 유사분열 시 핵공 해체의 근거다. 이 결과만으로 CDK5·p38/MK2, 분열하지 않는 ALS 운동뉴런 또는 제안된 사건 순서를 확정하지 않는다. 해당 연장은 가설이다.

[Fontoura et al.](https://pubmed.ncbi.nlm.nih.gov/10087256/)과 [Rosenblum/Blobel](https://pubmed.ncbi.nlm.nih.gov/10500183/)은 NUP98/NUP96 전구체 처리·자가 절단의 근거다. 여기서 도출한 점검 사항은 내인성 교체 실험에서 처리, 양, 위치와 정상 핵공 조립도 확인해야 한다는 것이다. 변이체가 수송을 바꿨다는 사실만으로 인산화의 원인성을 유일하게 특정하지 않는다.

전체 공개 ALS 작성 응답의 제한적 문자열 점검에서 두 자리 이상 숫자의 Ser/Thr/Tyr 위치 표기를 찾지 못했다. 이전 시험의 NUP62 표준 서열 위치 불일치를 이번에도 있었다고 보고하지 않는다. 이는 전체 단백질·서열·생물학적 검증이 아니다.

## AML: 선행 연구와 새 맥락

[Atovaquone AML 연구](https://pubmed.ncbi.nlm.nih.gov/31856268/)와 [2023 소아 AML 병용 연구](https://pubmed.ncbi.nlm.nih.gov/36831684/)는 이미 존재한다. 후자는 병용 가능성과 모델·상관 실험을 보고하지만, 이번 답의 특정 salvage 제한 잔존 세포에서 DHODH를 매개로 분화한다는 연결을 직접 입증하지는 않는다.

[Biswas et al., 2025](https://pubmed.ncbi.nlm.nih.gov/41061202/)는 teriflunomide를 HMA 저항성 TP53 변이 AML에서 연구했고, 분화와 일정에 따른 피리미딘 salvage 변화를 다룬다. 약물–DHODH–AML 분화 연결 자체를 새로운 발견으로 주장할 수는 없다. 다른 잔존 상태에 적용하는 가설의 신규성·타당성은 따로 확인해야 한다. 이번 제한적 확인은 선행 연구가 전혀 없다는 증명이 아니다.

## 승인·노출 확인

- [MEPRON 공식 라벨](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b426b6bf-f07e-4580-97ae-dfca1ddf5b8f)은 정해진 대상에서 atovaquone 현탁액의 Pneumocystis 폐렴 예방·치료 적응증을 확인한다. 단백질 결합률은 99.9%이며 엄밀한 ‘99.9% 초과’ 표현으로 확대하지 않는다.
- [MALARONE 공식 라벨](https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=fc22e8d8-3bfb-4f70-a599-dd81262a4887)은 atovaquone/proguanil 복합제의 말라리아 적응증을 확인한다. 복합제 적응증을 단일제 적응증으로 합치지 않는다.
- [EMA Arava](https://www.ema.europa.eu/en/medicines/human/EPAR/arava)는 성인의 활동성 류머티즘·건선성 관절염을 확인한다. [FDA 2024 leflunomide 라벨](https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/020905s033lbl.pdf)은 활동성 류머티즘 관절염을 명시한 자료로, 관할을 구분한다.
- [FDA 2026 teriflunomide 라벨](https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/202992s018lbl.pdf)은 성인의 재발성 다발성경화증 형태에 대한 적응증을 명시한다.

승인·높은 단백질 결합률 확인은 AML 효능이나 골수 유리 약물 노출을 측정한 결과가 아니다. 제안한 유리 EC50, 노출 창과 정상 조혈세포 선택성은 이번 자료에서 측정되지 않았다.

## 완료 AML 답의 검증 설계

최종 c006은 GPT의 atovaquone 가설과 GLM의 DHODH 가설을 Grok이 결합한 답이다. [2026 ScURA 연구](https://pmc.ncbi.nlm.nih.gov/articles/PMC12945687/)는 포유류 세포에서 효모 URA1의 세포질·fumarate 매개 피리미딘 합성과 호흡으로부터의 분리를 지지한다. 검증 도구의 논리를 뒷받침하지만 제안한 AML 상태의 분화·선택성까지 증명하지는 않는다. 이 자료는 외부 확인에만 사용했다.

1.5배, 70%, 2배, 15%포인트, 20%, 3배 등은 제안된 연구의 판단 기준이다. 실측·교정된 약리 수치나 이미 인정된 임상 기준으로 해석하지 않는다. 별도 LLM도 수치 기준의 문헌 근거 부족과 많은 단계로 인한 실행 부담을 지적했다.

[Etomoxir 원문 연구](https://pubmed.ncbi.nlm.nih.gov/29674640/)는 T세포에서 농도에 따른 비특이적 산화대사 영향을 보고한다. 여기서 도출한 점검 사항은 etomoxir 반응만으로 지방산 산화 의존성을 정의하려면 노출과 별개의 검증이 필요하다는 것이다. AML에서 같은 농도 경계가 성립한다거나 이번 가설이 틀렸음을 직접 입증한 것은 아니다.

독립 평가에서 구체성·검증 가능성 상승과 실행 가능성 하락이 함께 나타났다. 과학적 원인·새 발견·치료 효과 확인과 구분하며, 전문가 판단은 아직 대기 중이다.
