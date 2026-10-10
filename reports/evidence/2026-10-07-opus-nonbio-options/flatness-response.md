# flatness — Opus availability-probe public response

## hypothesis

Known: Dinh et al. (2017) showed that scaling a hidden unit's incoming weights by α and its outgoing weights by 1/α leaves a ReLU network's function unchanged but can change Hessian sharpness by any amount. Raw sharpness therefore cannot be a criterion at the level of the function. Hypothesis (an assumption, not a result): generalization tracks curvature after this symmetry is removed. Criterion: rescale each network to a canonical "balanced" form, where every hidden unit's incoming and outgoing weight norms are equal, then measure the Gauss-Newton trace. Proposed mechanism: this measures how much predictions change under perturbations proportional to each unit's scale, which reflects how fragile the function is rather than an artifact of the coordinates.

## prediction

Compare networks trained to the same low training loss. Balanced sharpness should rank-correlate with the generalization gap more strongly than raw sharpness, parameter norm or path norm.

## computational_test

Train about 200 ReLU MLPs on subsets of CIFAR-10, varying learning rate, batch size, width and label noise. Stop each at a fixed training loss. Counterexample check: apply random per-unit α∈[0.1,10], confirm the outputs are identical, and record how much the raw Hessian trace shifts. Then compute Kendall τ for each measure, both across all networks and within groups where only one hyperparameter changes.

## falsifier

The hypothesis fails if, within groups, balanced sharpness's τ is no higher than that of path norm or margin. It also fails if directly minimizing balanced sharpness (SAM in balanced coordinates) does not shrink the gap at matched training loss. Alternative explanation: logit margin or the implicit regularization from the learning rate could drive both quantities; control for this with partial correlation.

## limitations

Balancing removes only rescaling symmetry. It does not handle BatchNorm scale invariance or other reparameterizations. Correlation does not establish causation, and results on small MLPs may not transfer to larger models. Related invariant measures already exist, such as adaptive sharpness and the Fisher-Rao norm, and have shown mixed correlations with generalization. This is a test, not a new finding.
