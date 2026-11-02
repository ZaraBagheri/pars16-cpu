# Verification

The circuit suite was run successfully on **2026-11-02** using **Digital v0.31**, **Eclipse Temurin Java 17.0.21**, and Python 3 on macOS arm64. All **eight suites / 1,488 test rows** passed.

These are native simulator checks: the runner copies the `.dig` files into a temporary directory, generates Digital test-case tables, and invokes Digital's test engine. The schematic is the system under test. There is no replacement CPU emulator.

## Reproduce

Download and extract [Digital v0.31](https://github.com/hneemann/Digital/releases/tag/v0.31), install Java 8 or newer and Python 3, then run:

```sh
python3 scripts/verify.py --jar /path/to/Digital.jar
```

To select a Java executable explicitly:

```sh
python3 scripts/verify.py --jar /path/to/Digital.jar --java /path/to/java
```

Expected final line:

```text
PASS: eight circuit suites, 1488 native Digital test rows.
```

Without Digital, `python3 scripts/verify.py --static` checks XML, local subcircuit references, and agreement between the embedded demo ROM and `examples/demo.hex`. Static checks do not verify execution.

## Coverage

| Circuit | Rows | Checks |
| --- | ---: | --- |
| ALU | 240 | Arithmetic boundaries, signed overflow, carry/borrow, zero/negative flags, logic, all shift amounts, and unused function output |
| Condition evaluator | 32 | Every combination of condition, Z, N, and V |
| Sign extension | 1,024 | All ten-bit offsets, with every four-bit and seven-bit immediate also covered |
| Control unit | 16 | Every opcode's control outputs |
| Flag register | 35 | All flag patterns, enabled writes, held values, and reset |
| Register file | 84 | Writable registers, R0 write suppression, all operand-address pairs, debug reads, write enable, and reset |
| Data memory | 32 | Low/high addresses, clocked writes, held values, and independent debug reads |
| Complete CPU | 25 | Reset, demo execution checkpoints, load/store, condition pass/fail, taken branch, call/return, terminal loop, final registers, and retained RAM after reset |

The tests do not exhaust every CPU program or all ALU operand combinations. CPU integration coverage is the documented demo; component coverage is broader. There is no FPGA synthesis, timing, power, or hardware verification in this repository.

## Continuous integration

[The GitHub Actions workflow](../.github/workflows/verify.yml) runs the same suite on pushes and pull requests. It downloads the pinned Digital v0.31 release and checks the archive's SHA-256 before running the tests. Local execution has been verified; the hosted workflow will first execute after the repository is pushed to GitHub.

## Regenerate the schematic

```sh
python3 scripts/export_schematic.py --digital-jar /path/to/Digital.jar
```

This exports the actual top-level circuit through Digital's SVG renderer and normalizes its dimensions, background, and timestamp for repository display.

The component gallery uses the supplied module PNGs. To refresh its previews after replacing those images:

```sh
python3 scripts/prepare_image_gallery.py
```

The script embeds each original PNG unchanged in an SVG with a white background. It does not redraw or alter the circuit wiring.
