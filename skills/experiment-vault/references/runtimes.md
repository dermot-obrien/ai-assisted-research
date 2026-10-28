# Runtimes

A runtime is what a node's evidence runs must match so that the same experiment, given the same specification, gives the same result on any machine and any agent platform: your PC, a Claude Code session, a Cursor agent, a Codex task. It names the machine type, the exact Python build, the locked environment and the determinism settings, and it is written once in the vault. A node fixes its runtime at framing; from then on the vault refuses a backtest, holdout, forward or untracked run of that node on anything that does not match, and keeps an exploratory one with what differed. `<vault.py>` is `python <skills>/experiment-vault/bin/vault.py`. The steps agents follow are [the protocol](protocol.md), section 7.

No container and no central runner is needed. Almost every agent platform runs x86-64 Linux, and on that platform the causes of different numbers are known and each is removed: a different interpreter, different packages, different numeric code paths for different CPUs, different thread counts, and seeds left unset.

## What a runtime pins

| Part | Pinned by | Checked by |
|---|---|---|
| Machine type | `arch`, such as `linux-x86_64` | The interpreter's own platform |
| Python | The exact version and build string (`sys.version`), and whether it is uv-managed | The interpreter the run uses |
| Packages | The project's `uv.lock`, in the commit the capsule pins | `uv sync --frozen --check`: an extra, missing or different package refuses the run |
| Numeric settings | The determinism profile | The vault sets every variable itself, over whatever the caller set |
| CPU | The features the profile needs (AVX2 and FMA) | `/proc/cpuinfo` |
| Tolerance | `rtol` and `atol`, 0 by default | Every replay compares with them |
| Parity | Whether a result needs an identical replay on another machine or platform before its node's status moves | `vault.py parity` |

## Making one

1. The project is a uv project: `pyproject.toml` and a committed `uv.lock`, with `.venv/` in `.gitignore`.
2. Install a uv-managed Python, the same build on every machine: `uv python install 3.12.8`.
3. Build the environment and define the runtime from its interpreter:

   ```bash
   uv sync --frozen --python 3.12.8 --managed-python
   <vault.py> runtime create lx-py3128-v1 --python .venv/bin/python --profile cpu-deterministic-v1 --note "trading backtests"
   ```

4. Fix it on the node at framing: `dag_update.py --action set --node-id H-12.3 --field runtime --value lx-py3128-v1`.

A runtime is never changed. New packages, a new Python or another profile is a new runtime with a new name; nodes framed on the old one keep it.

`<vault.py> runtime check <name> --python .venv/bin/python` says whether this machine matches, and `runtime show [<name>]` what a runtime holds.

## The profiles

`cpu-deterministic-v1`, the default, sets:

| Variable | Value | Removes |
|---|---|---|
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `BLIS_NUM_THREADS` | `1` | Sums and products split over a varying number of threads, which add in a different order |
| `OPENBLAS_CORETYPE` | `Haswell` | OpenBLAS picking different kernels for different CPUs |
| `MKL_CBWR`, `MKL_ENABLE_INSTRUCTIONS` | `AVX2,STRICT`, `AVX2` | The same, for Intel's MKL |
| `NPY_DISABLE_CPU_FEATURES` | AVX-512 off, in the form the run's numpy accepts | numpy using AVX-512 code on CPUs that have it and AVX2 on those that do not |
| `PYTHONHASHSEED` | `0` | Set and dictionary order of strings changing between runs |
| `CUBLAS_WORKSPACE_CONFIG`, `TF_DETERMINISTIC_OPS`, `TF_CUDNN_DETERMINISTIC` | `:4096:8`, `1`, `1` | Non-deterministic GPU kernels, where the library offers a deterministic one |
| `TZ`, `LC_ALL`, `LANG` | `UTC`, `C.UTF-8` | Dates and text that depend on the machine's zone and locale |

It needs a CPU with AVX2 and FMA, which every x86-64 cloud machine of the last ten years has. The cost is speed: one thread, no AVX-512. `none` sets nothing and pins only the machine type, the interpreter and the packages.

The variables the profile set are recorded in the capsule's `run.env`, so a replay sets exactly the same.

## Writing experiments that give the same numbers anywhere

The runtime removes what the machine changes. What the code itself does still matters, and these rules make a result independent of the machine even where a library is not deterministic:

- **Money in integers.** Prices in ticks and P&L in integer units, or `decimal.Decimal`, never floats: integer arithmetic is the same on every machine. Convert to a float only for a reported ratio, and round it.
- **Sums in a fixed order.** Sort before summing anything whose order could vary (rows from a dictionary, files from a folder, results from a pool), and use `math.fsum` for sums of floats.
- **float64 throughout**, never float32 for a reported number.
- **No parallel reductions** whose order depends on scheduling (thread pools adding into one total, `multiprocessing` results summed as they arrive). Parallelise over independent units and combine them in a fixed order.
- **Every seed passed**, to every library that draws a random number, and recorded with `--seed`.
- **Metrics rounded at a precision fixed at framing**, and the decision rule applied to the rounded values, so a difference beyond that precision is a finding and one below it never decides anything.
- **No reading the clock or the network** inside a run; read the data's own dates.

## What cannot be made identical

- **GPU training.** Deterministic kernels narrow the differences but different GPUs still differ. A node that needs exact results runs on CPU, or fixes a tolerance at framing.
- **ARM machines** (an Apple Silicon Mac, ARM cloud instances): floating point differs from x86-64. A runtime pinned to `linux-x86_64` refuses them for evidence runs; use them for exploratory work.
- **Windows and macOS natively.** Run in WSL2 (Ubuntu) on a Windows PC, so the PC is x86-64 Linux like the cloud agents.

## Parity

A runtime with `parity` (the default) holds a result back until it has been replayed identically on another machine or agent platform in the same runtime: the original capsule was made in one place, and `vault.py replay <capsule>` in another gives `identical` with the runtime matched. `<vault.py> parity <node>/<capsule>` exits 0 when such a replay exists. The research flow's sync reads it before moving the node's status. A parity replay that does not come back `identical` is a finding: the node is `contested`, and the difference is what to look at.

## What each capsule records about where it ran

Every capsule now records `environment.machine`: the agent platform (`--tool`, else `VAULT_AGENT_TOOL`, else what the environment shows), the OS and its version, the architecture, the kernel, the C library, the CPU model and its relevant features, and the Python version and build. The DAG's capsule entry carries the platform, OS, architecture, CPU and Python, with the runtime's name and whether it matched, so a node shows where each of its results was made.
