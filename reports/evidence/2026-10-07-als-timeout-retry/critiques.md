# ALS 가설별 공개 비판 20건

## g0 · c001 · 평가자 grok

{"evidenceCoverage": 0.82, "specificity": 0.77, "novelty": 0.67, "actionability": 0.78}

- CDK1 is a mitotic kinase, and the write-up leaves its activation in post-mitotic motor neurons unspecified. Add a pore-localized CDK1 activity time course plus cell-cycle-entry markers, or substitute a kinase the same assays can show is active in these neurons.
- The ranked target is only partly specified: the TDP-43 variant is unnamed and Ser606 is explicitly unverified on the expressed isoform. Commit to a defined ALS allele, an isoform accession, and a sequence check that Ser606 is present and matches a CDK1 consensus before treating the site as the hypothesis.
- The falsifier and the stress-granule arm lack operational decision rules. Predefine the timepoints, the minimum loss of Ser606 occupancy, the import-rate margin that counts as unchanged, and a neuron-validated stress-granule perturbation together with the nongranular TDP-43-assembly measurements.

## g0 · c001 · 평가자 glm

{"evidenceCoverage": 0.84, "specificity": 0.88, "novelty": 0.8, "actionability": 0.88}

- The central molecular premise (NUP98 Ser606 as a direct, pathologically relevant CDK1 target in motor neurons) is admittedly drawn from unverified prior knowledge with zero support in the supplied packet; the entire residue-level hypothesis could rest on a misnumbered or non-physiological site. Fix: make the site nomination evidence-anchored by pre-registering the site-resolved NUP98 phosphoproteomics as a discovery step that can redirect the hypothesis to whichever early-changing, CDK1-dependent phosphorylation site is actually observed, rather than committing in advance to one unverifiable residue.
- The premise of 'sustained CDK1 activity' in post-mitotic spinal motor neurons is not separately labeled or justified, though it is as speculative as the phosphorylation step; aberrant CDK1 reactivation in neurons is itself an unvalidated bridging claim. Fix: add a dedicated premise check (e.g., validated CDK1 activity probe in edited and unedited patient versus isogenic neurons) with a pre-specified activity threshold, and treat neuronal CDK1 reactivation as its own assumption.
- The stress-granule discrimination arm central to falsifying S4 is underspecified: 'an approach validated for the neuronal system' names no intervention (e.g., G3BP1/2 double knockout versus a pharmacologic agent), so the decision rule 'rescue by that perturbation without early S606A protection favors sequestration' is not yet executable as written. Fix: name the specific stress-granule perturbation, its validation criteria in this neuronal system, and the quantitative effect-size/timing thresholds that would count as rescue.

## g0 · c002 · 평가자 gpt

{"evidenceCoverage": 0.89, "specificity": 0.72, "novelty": 0.64, "actionability": 0.73}

- Calling NUP98 a placeholder while leaving residues and kinase undefined weakens specificity. Add site-resolved phosphoproteomics in postmitotic motor neurons, then nominate the sites and kinase for causal testing.
- The novelty rests mainly on assigning phosphorylation a downstream-amplifier role; 'stabilizes pore disruption' lacks a distinctive molecular mechanism. Specify and test a change in NPC residence, partner binding, or permeability that distinguishes pore modification from continuing sequestration.
- The mutant comparisons are not decisive falsifiers without validation: phosphomimetics may not reproduce phosphorylation, and NUP98 replacement may independently disturb pores. Verify wild-type phosphorylation, matched expression, normal baseline transport, and comparable upstream assembly burden; add wild-type rescue and an orthogonal acute perturbation.

## g0 · c002 · 평가자 glm

{"evidenceCoverage": 0.75, "specificity": 0.85, "novelty": 0.78, "actionability": 0.8}

- Evidence gap at the core premise: nothing in the packet (or cited anywhere) shows NUP98 or any nucleoporin is phosphorylated in post-mitotic neurons, in stressed iPSC motor neurons, or in ALS tissue, and the triggering 'stress-responsive kinase' is an unnamed placeholder, so the amplifier step rests purely on an analogy to mitotic pore disassembly in dividing cells. Fix: run a pilot phosphoproteomics or phospho-NUP98 detection assay in the three iPSC arms before committing to the full design, and specify candidate kinases so an orthogonal inhibitor/phosphatase arm can be added.
- The central discriminator (endogenous replacement of NUP98 with non-phosphorylatable/phosphomimetic alleles) has unaddressed validity risks: Ser→Asp/Glu is an imperfect phosphate mimic and rewiring an essential FG-nucleoporin can alter pore composition and baseline transport, which would confound the 'same early phenotypes' comparisons the hypothesis depends on. Fix: verify endogenous-level expression, pore composition, and pre-stress import for each allele, and support the knock-in with an independent epistasis approach (e.g., kinase/phosphatase manipulation or site-specific base editing) rather than relying on one genetic perturbation.
- Specificity and resolution gaps: phosphorylation sites are only 'assumed CDK-consensus serines' with no residues mapped, the inducible cytoplasmic TDP-43 de-mixing construct is never defined, and the amplifier prediction of 'prolongation' of defects lacks pre-specified timepoints or effect-size decision thresholds. Fix: map the actual NUP98 phosphosites, name the induction method, and pre-register quantitative criteria for what counts as preservation of the early import dip versus prolongation.

## g0 · c003 · 평가자 gpt

{"evidenceCoverage": 0.88, "specificity": 0.8, "novelty": 0.78, "actionability": 0.76}

- The kinase and phosphorylation sites remain underspecified. Identify candidate Nup98 residues and the responsible kinase before interpreting perturbations; also label the proposed TDP-43 hyperphosphorylation-to-demixing sequence as untested rather than established by S3.
- Import failure does not demonstrate increased passive pore permeability, and stress-granule suppression cannot exclude S3’s granule-independent sequestration mechanism. Add size-resolved permeability assays, transport-factor localization, direct TDP-43-demixing perturbation, and a neuronal function or survival endpoint.
- Inducible TDP-43 stress risks imposing the proposed downstream event first, while an ineffective phosphomimetic is not a valid falsifier without functional validation. Test spontaneous disease-associated defects in defined ALS/control neurons, validate mutant behavior and baseline pore integrity, and include wild-type rescue.

## g0 · c003 · 평가자 grok

{"evidenceCoverage": 0.8, "specificity": 0.77, "novelty": 0.68, "actionability": 0.73}

- The allele-edit and kinase-rescue arms stay non-executable because the kinase is only a CDK-family class and the edits target unnamed “mitosis-regulated” or “candidate” sites. Name a minimal residue set, or add a site-mapping step with pre-registered acceptance criteria before editing, and tie one primary kinase to a genetic perturbation.
- S2 is restated as C9orf72 repeat RNA causing RanGAP mislocalization and as evidence that the Ran cycle is broadly vulnerable in ALS, and the causal chain cites S3 for cytoplasmic TDP-43 hyperphosphorylation as the step into demixing. Keep S2 as a C9orf72-restricted association, drop it from positive support for a TDP-43-proteinopathy initiator, and move TDP-43 hyperphosphorylation into the speculative bridges unless a packet sentence supports that order.
- Temporal precedence cannot be measured as written: “single-cell time resolution” is assigned to bulk NPC-IP phosphoproteomics, and “inducible TDP-43 stress” has no named inducer, dose, or clock. Separate live-cell imaging from bulk phosphoproteomics and pre-register a specific TDP-43 induction system with sampling windows anchored to the first detectable import change.

## g0 · c004 · 평가자 grok

{"evidenceCoverage": 0.86, "specificity": 0.81, "novelty": 0.67, "actionability": 0.86}

- Ser606 is named without a domain, motif, or biophysical reason that phosphorylation there would release NUP98 from the pore, so the residue is an unanchored label. Specify the NUP98 region and the proposed effect on FG cohesion or scaffold binding, or redefine the site as an empirical mass-spectrometry result rather than a fixed premise.
- S1 associates pore injury with insoluble TDP-43, while the predicted sequence places Ser606 phosphorylation before any cytoplasmic assembly. That reordering is only a speculative bridge and has no early assay of nuclear mutant-TDP-43 function. Add a pre-assembly nuclear readout, such as a TDP-43 splicing target tied to the kinase or phosphatase balance, that can fail while Ser606 occupancy is unchanged.
- The ranking lists PMID 26308891 with the TARDBP–NUP98 hypothesis although the text uses that study only as a non-equivalent C9orf72 route. Mark 26308891 as a boundary contrast and limit the supporting set to the TDP-43 pore and transport studies that actually motivate the test.

## g0 · c004 · 평가자 glm

{"evidenceCoverage": 0.85, "specificity": 0.87, "novelty": 0.76, "actionability": 0.88}

- The causal chain leaves its pivotal step a black box: it asserts that Ser606 phosphorylation 'weakens pore association' without any structural rationale (where Ser606 sits relative to the FG-repeat region or NUP96-anchoring domains) and without even a clearly labeled speculative kinase candidate for a post-mitotic neuron. Fix: map the residue within NUP98's pore-retention architecture and nominate a stress-activated kinase (e.g., GSK3beta or JNK) as a flagged assumption, paired with an inhibitor-rescue or kinase-occupancy arm that would give the TDP-43-to-phosphorylation bridge its own test rather than leaving it entirely inferred.
- The program bets everything on one unverified site selected from prior knowledge outside the packet: the strategy verifies the expressed sequence and quantifies occupancy, but if Ser606 proves undetectable or non-differential between mutant and corrected neurons there is no revision path. Fix: lead with unbiased comparative NUP98 phosphoproteomics across the isogenic pair to ground the site (or relocate it) empirically before committing to S606A engineering and phosphatase-recruitment lines.
- TDP-43-dependence of the phosphorylation change is tested only indirectly through the isogenic contrast, which cannot rule out that elevated Ser606 phosphorylation tracks generic mutant-cell burden (chronic proteostatic or metabolic stress) rather than a TDP-43-specific effect, and the design's general-stress readouts monitor this but do not resolve it. Fix: add a TDP-43-specific rescue arm, such as expression of a nuclear-retained WT construct in the mutant lines, to show phosphorylation normalization tracks TDP-43 nuclear dysfunction itself and not residual stress signatures.

## g1 · c005 · 평가자 grok

{"evidenceCoverage": 0.83, "specificity": 0.75, "novelty": 0.64, "actionability": 0.82}

- The causal chain names NUP98 but leaves the site (Ser606), kinase (JNK), and scaffold partner explicitly unanchored, so the claim is a mechanism class rather than one physical interaction. Pre-register a single site-selection rule, one scaffold protein for phosphate-sensitive binding, and treat every other site or kinase as exploratory.
- The initiating bridge from nuclear TDP-43 dysfunction to altered kinase/phosphatase output is not tied to a measured intermediate and stays collinear with generic mutant-cell stress. Name the splicing-reporter exons and regulator transcripts that must change, and require those changes to precede the drop in NUP98 site occupancy in the rescue time course.
- Support versus rejection has no quantitative threshold, so a nonspecific improvement in neuronal health could be read as evidence for pore-retention phosphorylation. Reject the hypothesis unless both orthogonal anti-phosphorylation interventions shift import-failure timing while ATP, passive permeability, granule burden, and assembly load stay inside a pre-set match to untreated mutant neurons.

## g1 · c005 · 평가자 glm

{"evidenceCoverage": 0.85, "specificity": 0.85, "novelty": 0.7, "actionability": 0.86}

- Core commitments are deferred rather than made: Ser606 is explicitly 'unanchored' and the kinase is left unresolved, so the 'hypothesis' as stated functions as a conditional phosphoproteomics screen rather than a single falsifiable NUP98-site claim. Fix by pre-specifying the anchor evidence for the site (motif compatibility, conservation, independent-site validation criteria with quantitative thresholds) and by declaring in advance which kinase assignment is part of the hypothesis versus a separable add-on, since the answer itself notes failure of the JNK arm would not reject the NUP98 hypothesis.
- The mechanistic direction is underspecified relative to the chosen target: NUP98 is an FG-nucleoporin central to nuclear-face scaffold contacts and mRNA export, yet the hypothesis frames the lesion almost solely as nuclear-import failure. Without planned mRNA-export-kinetic or nuclear-retention readouts, a retention defect could be misattributed to import cycles; add export-readout measurements and distinct predicted signatures for import-only versus export-coupled retention defects to sharpen the causal chain.
- The decisive falsification depends on intervention completeness that is never quantified: 'verified prevention' of phosphorylation with preserved baseline pore function lacks a pre-specified site-occupancy reduction threshold or an explicit expected outcome under partial suppression, which could produce ambiguous intermediate phenotypes. Fix by pre-registering occupancy dose-response targets for both the phospho-resistant knock-in and the phosphatase-recruitment arm, with stated predictions for partial-versus-complete suppression.

## g1 · c006 · 평가자 gpt

{"evidenceCoverage": 0.91, "specificity": 0.84, "novelty": 0.78, "actionability": 0.82}

- Evidence coverage is unusually careful: all four sources are used with their boundaries intact, and phosphorylation assumptions are explicitly separated from supported findings. However, the upstream splice regulator/phosphatase remains unnamed; specify a candidate transcript, splice event, and isoform-rescue test.
- CDK consensus, kinase occupancy, and CDK1 loss-of-function cannot establish direct CDK1 phosphorylation or exclude indirect stress effects. Validate exact sites with purified kinase, then combine acute CDK1 perturbation with NUP98-site epistasis.
- The site gate permits phosphorylation 'at' t0, whereas the falsifier requires precedence; bulk sampling also obscures cell-wise ordering. Define temporal resolution and detection limits consistently, and measure Ran/NTF2 flux alongside permeability to distinguish increased leakage from impaired active transport.

## g1 · c006 · 평가자 glm

{"evidenceCoverage": 0.9, "specificity": 0.85, "novelty": 0.75, "actionability": 0.85}

- The CDK1-activation step is asserted but not testable as written: 'a CDK1 regulator or an opposing phosphatase' is never named, so the causal link from nuclear TDP-43 dysfunction to CDK1 activity on NUP98 is flagged as a bridge but has no manipulable molecular target or pre-registered order requirement of its own. Fix by naming candidate splicing targets (e.g., CDC25-family/Wee1-family transcripts or a known TDP-43 splicing substrate with CDK-axis function), requiring the splicing lesion to temporally precede NUP98 phosphorylation, and adding a rescue or occlusion experiment that normalizes CDK1 activity before the upstream bridge is accepted.
- Causal-order detection is doubly vulnerable: t0 is defined retrospectively as the first sampled window with import divergence, so phosphorylation arising between windows is missed or misordered, and low-stoichiometry FG-region sites in bulk NPC phosphoproteomics may fall below detection, making the primary falsifier ('no qualifying FG-region phosphorylation precedes t0') prone to false negatives. Fix with denser time-course sampling around maturation, targeted LC-MS/MS (PRM/SRM) against synthetic phospho-peptide standards for candidate sites, and an acute, timed pre-t0 CDK1-inhibition window that must abolish the t0 transport lesion for the bridge to stand.
- The in-cell sufficiency arm hinges on a phosphomimetic, but S->E substitution does not reproduce a phosphate's charge density or dynamics, which are exactly the properties the FG-cohesion/permeability mechanism depends on; an in vitro-validated mimetic therefore establishes the sufficiency of the mimetic, not of the native phosphosite at the native pore. Fix by adding an acute in-cell sufficiency test, e.g., a NUP98-targeted kinase-recruitment module or analog-sensitive CDK1 allele that installs and reverses the native modification on demand, with the phosphomimetic retained only as a lower-bound approximation.

## g2 · c007 · 평가자 gpt

{"evidenceCoverage": 0.88, "specificity": 0.83, "novelty": 0.78, "actionability": 0.76}

- The WEE1 cassette exon remains unidentified, and exon-included Wee1 rescue could bypass rather than establish the splice mechanism. Define the transcript/exon, verify its functional consequence, and test endogenous splice correction plus reciprocal exon skipping.
- NUP98-targeted enzymes may modify neighboring substrates, while reporters and total Ran localization do not directly establish Ran-gradient collapse. Test recruitment in phospho-resistant cells, profile nearby phosphosites, and measure compartment-specific Ran-GTP.
- Twenty-four-hour sampling may miss or misorder rapid phosphorylation, sequestration, and transport changes. Use denser sampling around onset and validate the proposed phospho-signal before interpreting temporal precedence.

## g2 · c007 · 평가자 glm

{"evidenceCoverage": 0.78, "specificity": 0.88, "novelty": 0.7, "actionability": 0.8}

- The causal chain is built almost entirely from explicitly unverified prior knowledge (TDP-43 controlling a WEE1 cassette exon, WEE1 loss activating CDK1 in postmitotic neurons, interphase CDK1 phosphorylating NUP98 FG/GFLG enough to raise passive permeability in an assembled pore), so the hypothesis has almost no supported content beyond the 'TDP-43 disrupts pores' premise; to strengthen it, attach at least one external line of evidence (e.g., any published TDP-43 splicing-target screen, neuronal cyclin B/CDK1 expression data, or in vitro NUP98 FG phosphorylation data) to each bridge, and rank the bridges by weakness, testing the weakest first.
- The central quantitative readout is not actually executable as specified: phospho-site mapping and stoichiometry of repetitive FG/GLFG peptides on endogenous NUP98 by PRM/SRM is unreliable because low-complexity repeated peptides identify and quantify poorly, and the same-cell 'FG-NUP98 phospho-signal' presumes an antibody that does not exist for a hypothetical site; the plan should state an alternative (e.g., knock-in epitope- or phospho-mutant-tagged NUP98 alleles, enrichment with engineered probes, or permeability readouts on phospho-null knock-ins) before making sub-LOD 'stop engineering' decisions the binding outcome.
- The experimental program is overpacked with no prioritization: epistatic knock-in alleles, analog-sensitive CDK1 knock-in, NUP98-directed phosphatase recruitment, inducible CDK1 recruitment to endogenous NUP98, and roughly a dozen readouts per 24-h window exceed realistic single-lab scope; the fix is to define a minimal single experiment that alone can kill or advance the hypothesis (t0-anchored time course of WEE1 junction, CDK1-Tyr15, and one permeability readout with phospho-site mapping only if a signal appears), deferring the sufficiency-engineering arms until that screen is passed.

## g2 · c008 · 평가자 gpt

{"evidenceCoverage": 0.86, "specificity": 0.88, "novelty": 0.8, "actionability": 0.79}

- The upstream mechanism has a sign problem: WEE1 inhibits CDK1, whereas CDC25C normally activates it. Specify the proposed splice products and their functional effects, and test endogenous splice correction rather than relying on WEE1 overexpression.
- Concurrent permeability and Ran measurements do not establish FG leakage as the mediator rather than broader pore disassembly or parallel stress. Measure NPC structural integrity and test whether restoring the Ran gradient rescues import despite retained NUP98 phosphorylation.
- Some falsifiers overinterpret negative results. Synthetic peptide standards establish sensitivity for assayed peptides, not exhaustive FG-region phosphosite coverage; failed inhibition or rescue also requires verified target engagement. Define validated site coverage and perturbation efficacy before treating these outcomes as falsification.

## g2 · c008 · 평가자 grok

{"evidenceCoverage": 0.82, "specificity": 0.84, "novelty": 0.73, "actionability": 0.81}

- The opening causal chain is written as an occurring mechanism (mis-splicing, NUP98 phosphorylation, Ran-gradient collapse, then demixing) even though the packet supports only TDP-43-linked transport and pore defects. Recast every non-packet link as a conditional prediction and keep S1–S4 claims inside the supported-premise list.
- WEE1 loss and CDC25C loss push CDK1 in opposite directions, and no FG residue or splice isoform is fixed before the phosphoproteomic grid, so a post-hoc “qualifying” site can be fit to t0. Pre-register the net CDK1-pY15 direction, the WEE1 and CDC25C isoforms, and one primary CDK-consensus NUP98 FG residue, with extra sites as a multiplicity-controlled secondary set.
- FG leak, Ran/NTF2 gradient loss, and active import failure are treated as one initiating lesion, yet RanGAP mislocalization and transport-factor sequestration can collapse import with an intact FG barrier. Make the decisive falsifier a dissociation on the same clock: phosphorylation blocked and size-selective permeability preserved while Ran flux and NLS import still fail.

## g3 · c009 · 평가자 gpt

{"evidenceCoverage": 0.87, "specificity": 0.78, "novelty": 0.76, "actionability": 0.67}

- The supposedly preregistered WEE1 exon and NUP98 phosphosite remain unidentified; CLIP support does not establish an inhibitory splice isoform, and the CDC25B fallback changes the mechanism. Separate target discovery from confirmation, then lock one functionally validated isoform–site hypothesis.
- CDK1 recruitment or analog-sensitive CDK1 cannot establish site-specific sufficiency because other substrates may be phosphorylated. Lack of additional inhibitor benefit can also reflect a ceiling effect. Require the phospho-resistant NUP98 allele itself to prevent the lesion and block recruitment-induced defects, with preserved baseline pore function and collateral-phosphorylation controls.
- NTF2 nuclear accumulation conflates influx with passive leakage, and neuronal dysfunction lacks a defined endpoint. Measure directional transport kinetics and Ran nucleotide states, then test whether site-specific rescue preserves motor-neuron function or survival independently of general stress.

## g3 · c009 · 평가자 glm

{"evidenceCoverage": 0.84, "specificity": 0.9, "novelty": 0.79, "actionability": 0.88}

- The upstream WEE1-splice bridge is doubly unverified: no supplied or cited source connects TDP-43 dysfunction to WEE1 splicing or to CDK1 reactivation in TARDBP-mutant neurons, and the 'pre-registered splice event' is defined only by a future selection rule with a CDC25B fallback that would swap the regulatory logic (loss of inhibitor versus gain of activator). Fix by committing to a named exon (or releveling the registered hypothesis to CDK1 reactivation from any upstream cause) before the timecourse is fixed, and state the CLIP-support threshold quantitatively.
- The hard falsifier 'CDK1 inhibition still rescues transport on phospho-resistant NUP98' can wrongly kill a true hypothesis if multiple CDK1-consensus sites on NUP98 (or another CDK1 substrate within the pore/transport machinery) contribute to the lesion; the limitations concede hidden extra sites and kinases, but the decision rule does not require a multi-site resistance panel before firing. Fix: make single-site non-suppression non-decisive and trigger the falsifier only after a pre-specified combinatorial phospho-resistant allele test.
- The 'initiator' claim that permeability and Ran/NTF2 defects precede cytoplasmic TDP-43 demixing rests on an unpowered null: early sub-microscopic demixing or stress granules could occur between the 12-hour bins, since detection floors are pre-registered only for phosphorylation and not for assembly readouts. Fix: add a high-sensitivity early TDP-43-mobility or oligomerization assay (e.g., FLIP/FRAP or single-molecule imaging) with its own pre-registered detection floor so 'before assemblies' becomes an informative absence rather than an insensitive one.

## g3 · c010 · 평가자 gpt

{"evidenceCoverage": 0.89, "specificity": 0.87, "novelty": 0.79, "actionability": 0.79}

- The proposed upstream acceptance test does not establish that mis-splicing activates CDK1: downstream kinase inhibition could also rescue stress-driven activation. Identify the specific exon/isoform, repair it in mutant neurons, and reproduce the lesion in corrected controls.
- In-cell sufficiency remains confounded by other CDK1 or nearby pore substrates; analog-sensitive kinase inhibition also does not itself reverse phosphorylation. Require site-dependent sufficiency in the phospho-resistant background, profile neighboring substrates, and directly verify dephosphorylation.
- Cohort-aligned phosphoproteomics and live import imaging may misorder events across heterogeneous neurons. Link longitudinal transport measurements to indexed, site-specific phosphorylation measurements in the same cells before treating temporal precedence as established.

## g3 · c010 · 평가자 grok

{"evidenceCoverage": 0.81, "specificity": 0.84, "novelty": 0.72, "actionability": 0.8}

- The phosphorylation claim is limited to the NUP98 FG/GLFG region, and the upstream bridge is an open disjunction (WEE1, CDC25A/C, or any splice-regulated CDK transcript), so both arms can be redefined after the data arrive. Pre-register a short primary list of NUP98 FG-domain CDK1 residues and one primary mis-spliced exon, and treat every other site or transcript as exploratory.
- S1 and S3 link nucleoporin and import defects to TDP-43 aggregates or cytoplasmic demixing, yet those papers are still used as the backdrop for a pre-assembly initiating lesion. State that S1–S4 give no temporal support for that order, and require same-cell evidence that FG-region phosphorylation and the Ran lesion precede cytoplasmic assemblies.
- Partial CDK1 activity in postmitotic neurons is not separated from abortive cell-cycle re-entry, which would hit many mitotic substrates and favor pore disassembly rather than selective FG weakening. Add a pre-registered negative panel (cyclin B1 localization, phospho-lamin, phospho-Rb, non-FG nucleoporin sites) and require FG-restricted, sub-disassembly stoichiometry at t0.
