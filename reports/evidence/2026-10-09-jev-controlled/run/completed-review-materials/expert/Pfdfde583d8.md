# Pfdfde583d8

**Hypothesis title:** Nup153 FG-domain phosphorylation as a required pore-level mediator linking TDP-43 cytoplasmic de-mixing to nucleocytoplasmic transport failure in TDP-43 proteinopathy-associated ALS

**MECHANISM AND SUPPORTED PREMISES**

Supported by the packet: (i) TDP-43 pathology correlates with nucleoporin mislocalization and impaired nucleocytoplasmic transport in ALS tissue and cell models [S1]; (ii) cytoplasmic TDP-43 assemblies, independent of classical stress granules, impair nuclear import and deplete nuclear TDP-43 [S3]; (iii) stress-granule assembly sequesters transport factors and impairs transport [S4] — S4 documents sequestration-linked impairment only; labeling this route phosphorylation-independent is my assumption, not a supported premise; (iv) C9orf72 repeat expansion impairs transport via repeat-RNA mechanisms [S2], establishing context-dependence; I scope the hypothesis to TDP-43 proteinopathy ALS and do not extrapolate to C9orf72.

Causal chain (status labeled): (1) Cytoplasmic TDP-43 de-mixes in susceptible motor neurons — S3 supports cell-level sufficiency, but whether this initiates human ALS in vivo is an assumption the packet cautions against universalizing. (2) Assumption: de-mixed TDP-43 or its stress activates or recruits a pore kinase (identity unknown; MAPK candidacy is unverified prior knowledge). (3) Core hypothesis (assumption): this kinase phosphorylates nuclear-basket Nup153 at FG-repeat/linker serine/threonine residues, destabilizing Nup153 docking or importin-β/Ran contacts, impairing pore function even for Nup153 copies not physically occluded by aggregates. The packet names no specific nucleoporin; Nup153 selection rests on unverified prior knowledge (basket position, FG domain, importin-β/Ran interactions), and Nup50, Nup62, Nup98, Tpr, and Nup358 are equally plausible a priori candidates. (4) Assumption: phosphorylation amplifies the defect beyond stoichiometric sequestration, pushing dysfunction past a threshold that depletes nuclear TDP-43 and creates a feed-forward loop. (5) Consistent with S1 and S3: sustained transport collapse and nuclear TDP-43 depletion impair RNA processing, driving motor-neuron death.

**INITIATING VS. DOWNSTREAM**

S3 shows TDP-43 de-mixing can drive transport defects in cells; in vivo initiation is labeled an assumption. Nup153 phosphorylation is proposed as the pore-level proximal cause of transport failure, not a passive stress bystander.

**ALTERNATIVE EXPLANATION**

Sequestration-only model, framework consistent with S4: aggregates and stress granules physically sequester transport factors, causing transport failure by stoichiometric depletion; any observed phosphorylation is a non-causal bystander. Whether S4's sequestration is phosphorylation-independent is not established and is an assumption embedded here. In this model, preventing phosphorylation does not rescue transport.

**SPECULATIVE BRIDGES (assumptions)**
- Nup153 phosphorylation at FG/linker sites in ALS motor neurons (not established).
- Necessity of this phosphorylation for the transport defect (not established).
- A specific kinase recruited or activated by de-mixing (not established).
- Phosphorylation sufficiency without aggregates (not established).
- In vivo initiation by TDP-43 de-mixing (S3 supports cell-level sufficiency only).
- Nucleoporin phosphorylation regulates NPC assembly/disassembly in mitosis (unverified prior knowledge).

**DISCRIMINATING PRECLINICAL TEST STRATEGY**

Step 0 — Unbiased NPC-wide phosphoproteomic survey on affinity-purified pores from aggregate-bearing vs. control motor neurons; commit to Nup153 as the named target only if it is a top phosphorylated nucleoporin, otherwise shift the target identity while retaining the same logic.

Step 1 — Inducible TDP-43 de-mixing in human iPSC-derived motor neurons. Add human-context corroboration: patient iPSC neurons and/or post-mortem ALS tissue co-stained for de-mixed TDP-43, transport-factor localization, and phospho-Nup153 (once a site-specific antibody exists) — correlative, not causal.

Step 2 — Map Nup153 phosphosites by phosphoproteomic mass spec on immunoprecipitated Nup153 ± de-mixing induction; extend mapping across the basket/fibrillar nucleoporin neighborhood (Nup50, Tpr, others) to guard against redundant phosphorylation masking a Nup153-only effect.

Step 3 — Core discriminating experiment, with quantitative endpoints relative to a pre-registered no-aggregate WT baseline:
- Necessity: knock in phospho-null Nup153 (S/T→A at all mapped sites; interpret only if ≥80% of detected sites are covered, otherwise report partial coverage). Full-rescue prediction (phosphorylation dominant): NLS-GFP flux and nuclear TDP-43 retention restored to ≥80% of baseline. Partial-rescue prediction (phosphorylation is one mediator alongside ongoing physical sequestration of other pore factors): restoration of ≥40% but <80% above a WT-rescue control. No rescue (<20% above WT-rescue baseline) disfavors necessity and supports the sequestration-only alternative.
- Sufficiency: express phospho-mimetic Nup153 (S/T→D/E) in aggregate-free neurons. Because S/T→D/E is a weak mimic at protein-contact interfaces (charge substitution lacks phosphate's steric bulk), a negative result alone does not reject sufficiency. Add orthogonal confirmation: (a) site-specific phospho-Nup153 antibodies on endogenous Nup153 in aggregate-bearing neurons, and (b) kinase-driven phosphorylation of purified Nup153 or permeabilized-cell NPC, mass-spec confirmed, followed by quantitative NLS-import. Sufficiency is considered unmet only if kinase-phosphorylated Nup153 also fails to impair import.
- Sequestration control (pure stress-granule paradigm per S4, without TDP-43 de-mixing; phospho-null vs. WT Nup153): Branch A — phospho-null restores SG-impaired transport above the partial threshold, implying phosphorylation contributes in the SG context too; this would re-scope the mechanism from TDP-43-specific to a general pore-phosphorylation mediator. Branch B — phospho-null fails to rescue, implying stoichiometric sequestration dominates the SG context [S4] and supporting phosphorylation specificity to the TDP-43 de-mixing route [S3]. Report effect sizes, not binary outcomes.

Step 4 — Temporal: live imaging of phospho-Nup153 signal and NLS flux after de-mixing induction at single-cell resolution. A phospho-Nup153 rise preceding detectable import decline supports a mediator role; signal appearing only after import falls favors a bystander interpretation.

**FALSIFYING OBSERVATION**

In aggregate-bearing motor neurons with NLS-GFP flux reduced ≥50% vs. no-aggregate control, replacing endogenous Nup153 with a phospho-null variant properly localized at endogenous levels (≥80% phosphosites covered) fails to restore import flux beyond the partial-rescue threshold (<20% above WT-rescue baseline), while mass spectrometry of kinase-phosphorylated Nup153 in a parallel permeabilized-cell assay confirms the tested sites are phosphorylated, and kinase-phosphorylated Nup153 fails to impair transport in aggregate-free neurons. Together this shows Nup153 phosphorylation is neither necessary nor sufficient, falsifying the hypothesis for this ALS subtype.

**LIMITATIONS**

Phospho-null substitutions may perturb Nup153 structure independently of dephosphorylation. Other nucleoporins may also require phosphorylation for the full defect, so Nup153-only rescue may be partial. Scoped to TDP-43 proteinopathy ALS; does not address C9orf72 [S2]. iPSC motor neurons may miss chronic aging context; human-tissue co-staining is correlative only. The responsible kinase may act on multiple substrates, limiting inhibitor-based discrimination. The in vivo initiating role of TDP-43 de-mixing remains an assumption.
