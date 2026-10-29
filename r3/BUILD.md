# R3: how Qiskit 2.6.1 and the 15 faults were built

**Source.** Qiskit tag `2.6.1` from https://github.com/Qiskit/qiskit (commit of the tag in a clone fetched on 2026-10-29).

**Toolchain.**
- **Rust:** stable `rustc 1.97.0` (2026-07-07). The repository pins Rust 1.89 in `rust-toolchain.toml`, which could not be downloaded in the build environment, so `RUSTUP_TOOLCHAIN=stable` overrides it. Every build (clean and faults) uses the same toolchain.
- **Python and platform:** Python 3.13, setuptools-rust, Ubuntu with glibc 2.39, x86_64.
- **Build profile:** Qiskit's own release profile (`lto = "fat"`, `codegen-units = 1`) and default features (`cache_pygates`).

**Build commands.**
- **Clean wheel:** `pip wheel --no-deps --no-build-isolation .` in the source tree. The output is `qiskit-2.6.1-cp310-abi3-linux_x86_64.whl`.
- **Fault wheels:** `r3/make_faults.py`. It copies the pristine source to a fixed work path, reverses the fault's patch (`git apply -R`) and builds with the same command, toolchain and target directory. For a Python-only fault, the overlay is the reverted Python files and no build is needed.

**Check against PyPI.** Before registration, our clean build compiled the 116 corpus units with the frozen baseline transpiler (`PYTHONHASHSEED=0`). The fingerprints (`obsaware.oracles.fingerprint`) equalled those of the PyPI 2.6.1 wheel for all 116 units.

**Costs.** Our build may run at a slightly different speed from the PyPI wheel, because of the newer compiler. All R3 costs (estimate and charges) are measured on our build, so this affects neither the comparisons nor the claims.

**Wheelhouse.** `r3/make_wheelhouse_r3.py` combines our Qiskit wheel with PyPI wheels:
- Qiskit Aer 0.18.0;
- numpy 2.5.4, scipy 1.18.1, PyYAML 6.0.3, psutil 7.2.2 and pandas 3.1.0, as in the R2 2.3.1 wheelhouse;
- their dependencies.

The hashes of every wheel are in `r3/wheelhouse.sha256`.
