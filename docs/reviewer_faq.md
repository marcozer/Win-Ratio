# Reviewer FAQ

## Why is the committed cohort synthetic?

The AFC registry is governed clinical data with direct and indirect disclosure risks. A public code repository is not an approved data-release mechanism.

## Does the code implement the current hierarchy?

Yes. It places major complications before CR-POPF, stops when both records have a terminal death, supports graded severity, and implements exact-day, clinical-margin, categorical, and no-LOS variants.

## Does matching silently impute missing covariates?

No. Complete-case estimation is the default. Simple imputation is opt-in and clearly labeled; multiple imputation must be performed as a separate prespecified workflow.

## Is the reported tier contribution a component effect?

No. A tier is reached only when every higher-priority tier ties. Tier counts localize first resolution and are conditional descriptions.

## Does more resolved-pair information imply greater power?

No. Information rate and statistical efficiency are distinct. Power depends on the effect mechanism, hierarchy, correlation, margins, and competing binary thresholds.

## How is center-level uncertainty handled?

The package can resample centers within exposure arm, refit the propensity score, rematch or reweight, and recompute the endpoint. The committed synthetic run uses fewer replicates than the protected analysis for practical repository execution.
