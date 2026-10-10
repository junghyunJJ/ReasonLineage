# grokking — Opus availability-probe public response

## hypothesis

Known: Nanda et al. (2023) reported that grokked modular-addition transformers use a sparse set of Fourier frequencies, and that a "restricted loss" fell before test accuracy rose. Liu et al. (Omnigrok) linked grokking to shrinking weight norm. Hypothesis (assumed, and only for this setting): during the plateau, a partial Fourier circuit already exists. Test accuracy stays low because high-norm memorization components outweigh it in the logits. The delay is therefore set by how fast those components are cleaned up. Weight norm drops at the same time, but the hypothesis says the norm is not the cause.

## prediction

At plateau checkpoints, keeping only the dominant Fourier frequencies of the current checkpoint should raise test accuracy well above chance. This should happen well before test accuracy rises on its own.

## computational_test

Across 3 or more seeds, save checkpoints throughout the plateau. Apply three interventions: (a) project the embedding, unembedding and MLP output onto the top-k frequencies, with k chosen from that checkpoint alone; (b) project onto k random frequencies, scaled to match the norm reduction of (a); (c) uniformly rescale the weights to match the norm after (a). Compare logits with temperature calibration. As a training-time version, apply (a) or (c) periodically and measure the change in grokking time. The norm-causal alternative predicts (c) ≈ (a).

## falsifier

The hypothesis is wrong if (a) gives no test gain until accuracy is already rising on its own, or if (c) or (b) match the effect of (a).

## limitations

Results cover one task and architecture. Projection pushes activations off-distribution, and choosing frequencies could leak information. Rescaling also changes the effective softmax temperature. A positive result shows that a masked circuit is enough to generalize, not that it explains grokking in general.
