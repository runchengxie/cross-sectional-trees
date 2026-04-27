## ADDED Requirements

### Requirement: Models are resolved through a registry

Supported model types SHALL be resolved through a central registry that defines
aliases, default parameters, estimator construction, fit behavior, and feature
importance behavior.

#### Scenario: Existing model alias is resolved

- **WHEN** a config uses an existing supported model alias
- **THEN** model normalization resolves it to the same canonical model type as
  before the registry change

#### Scenario: Default parameters are requested

- **WHEN** a supported model is configured without explicit parameters
- **THEN** the registry supplies the same effective default parameters as the
  previous implementation

### Requirement: Model fit behavior is model-specific

The registry SHALL preserve model-specific fit behavior, including ranker query
groups and sample-weight handling.

#### Scenario: XGBoost ranker is fit

- **WHEN** an `xgb_ranker` model is fit
- **THEN** the fit path sorts by date, constructs query groups, and converts row
  sample weights to group weights when required

#### Scenario: Regressor model is fit

- **WHEN** a non-ranker supported model is fit
- **THEN** the fit path uses the configured feature columns, target column, and
  optional row-level sample weights

### Requirement: Feature importance is registry-aware

Feature-importance extraction SHALL use model-specific registry behavior when
available and fall back to the existing generic `feature_importances_` or
absolute `coef_` behavior otherwise.

#### Scenario: Tree model has feature importances

- **WHEN** a fitted tree model exposes `feature_importances_`
- **THEN** the output frame reports those values with the existing feature order
  and source semantics

#### Scenario: Linear model has coefficients

- **WHEN** a fitted linear model exposes `coef_`
- **THEN** the output frame reports absolute coefficient-based importance with
  the existing source semantics

### Requirement: Existing modeling helpers remain compatible

Existing helper functions in `cstree.modeling` SHALL retain their public names
and return shapes during the registry migration.

#### Scenario: Existing caller builds a model

- **WHEN** existing code calls `resolve_model_spec`, `build_model`,
  `build_model_from_config`, `fit_model`, or `feature_importance_frame`
- **THEN** the helper remains available and returns compatible values for all
  currently supported model types
