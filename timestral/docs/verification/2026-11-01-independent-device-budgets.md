# Independent cross-device budget validation

The proposed `5e-4 * max(abs(CPU), 1)` budget is **rejected** as a general
CPU/GPU equivalence criterion. It failed independent data-scale tests on every
model/vendor combination. No new tolerance has been adopted and GPU promotion
remains blocked.

The direct-upstream diagnostic uses a new random seed and nine history families:
trend, seasonal, random noise, steps, constant, zero, missing observations, grouped
rows and disabled boolean options. Each family is tested at scales 0.001, 1 and
1000 and horizons 160 and 1024: 54 cases per combination, 216 total. Inputs and
options are identical for independent upstream CPU/GPU calls; no serving code or
forecast algorithm is substituted. Covariates are covered by the earlier hardware
matrix, but not independently broadened by this experiment.

| Backend | Model | Unit-floor budget passes | Input-scale-floor budget passes | Maximum input-scale-normalized error |
| --- | --- | --- | --- | --- |
| cuda | 5M | 45/54 | 52/54 | 0.000734545 |
| cuda | 209M | 47/54 | 54/54 | 0.000141271 |
| rocm | 5M | 45/54 | 54/54 | 0.000466505 |
| rocm | 209M | 46/54 | 54/54 | 7.28408e-05 |

The second experimental metric uses `abs(GPU - CPU) / max(abs(CPU), input_scale)`.
It demonstrates why an absolute unit floor does not transfer safely between
measurement scales. It is not a production policy: `input_scale` here is the known
synthetic generator amplitude, not an estimator from arbitrary real requests.
Even this alternative exceeded 0.05% for NVIDIA 5M grouped 1024-step forecasts.

The [raw metrics](2026-11-01-independent-device-budgets.json) pin the script,
image/model/source identities and every output error. The earlier result that the
server is bitwise identical to unchanged upstream on the same device remains
valid for that tested matrix. Cross-device numerical behavior is a separate
question. Keep GPU images experimental and preserve CPU references; do not widen
a threshold simply to make these tests green. A revised policy requires an
explicit data-scale definition and additional independent validation.
