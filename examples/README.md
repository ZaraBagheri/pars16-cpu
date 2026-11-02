# A small program that exercises the CPU

The instruction ROM in `circuits/Pars16.dig` contains this 16-word program.
[`demo.hex`](demo.hex) is the same program in Digital's `v2.0 raw` memory format.
The mnemonics below describe the encoding; this repository does not require an
assembler. See the [instruction-set reference](../docs/instruction-set.md).

The program adds 5 and 7, stores 12 to data memory, loads it back, and compares
the loaded value with the sum. It then demonstrates a conditional instruction
that executes, one that is skipped, a taken conditional branch, a subroutine
call through R7, and a register-indirect return.

| Address | Word | Instruction | Effect |
| --- | --- | --- | --- |
| `00` | `2885` | `LI R1, 5` | R1 = 5 |
| `01` | `2907` | `LI R2, 7` | R2 = 7 |
| `02` | `0195` | `ADD.S R3, R1, R2` | R3 = 12; flags = 0 |
| `03` | `2580` | `ST R3, [R0 + 0]` | memory[0] = 12 |
| `04` | `2200` | `LD R4, [R0 + 0]` | R4 = 12 |
| `05` | `06c7` | `SUB.S R5, R4, R3` | R5 = 0; Z = 1 |
| `06` | `6b01` | `LI.Z R6, 1` | Executes because Z = 1 |
| `07` | `ab02` | `LI.N R6, 2` | Skipped because N = 0 |
| `08` | `7001` | `B.Z +1` | Branch to `0A`, skipping `09` |
| `09` | `2b03` | `LI R6, 3` | Skipped by the branch |
| `0A` | `3402` | `JAL +2` | R7 = `000B`; branch to `0D` |
| `0B` | `3003` | `B +3` | Branch to `0F` after returning |
| `0C` | `3c00` | `NOP` | Unused padding |
| `0D` | `1f61` | `ADDI R6, R6, 1` | R6 = 2 |
| `0E` | `3b80` | `JR R7` | Return to `0B` |
| `0F` | `33ff` | `B -1` | Stay at `0F` |

Branch offsets are relative to the following instruction (`PC + 1`).
`.S` requests a status-flag update. `.Z` and `.N` predicate the instruction
on the stored zero and negative flags. Arithmetic wraps to 16 bits.

## Run it interactively

1. Open `circuits/Pars16.dig` in Digital and start simulation.
2. Keep `DBG_EN=0` while running. Set `CLK=0`, set `RESET=1`, then change
   `CLK` to 1 and back to 0. Reset is synchronous and needs a rising edge.
3. Set `RESET=0`. Each change of `CLK` from 0 to 1 executes one instruction;
   return it to 0 before the next step.
4. After **13 execution rising edges**, `PC_OUT=0F`. More execution edges
   remain in the terminal loop. This is a loop, not a halt instruction.
5. Select `DBG_RSEL` from 0 through 7 to inspect `DBG_ROUT`. Set
   `DBG_MADDR=0` to inspect `DBG_MOUT`. You can keep `DBG_EN=0` for these
   dedicated debug outputs.

The PCs after each of the 13 execution edges are:

```text
01 02 03 04 05 06 07 08 0A 0D 0E 0B 0F
```

Expected final state (all values hexadecimal):

| Signal | Value |
| --- | --- |
| R0 | `0000` |
| R1 | `0005` |
| R2 | `0007` |
| R3 | `000C` |
| R4 | `000C` |
| R5 | `0000` |
| R6 | `0002` |
| R7 | `000B` |
| memory[0] / `DBG_MOUT` at address 0 | `000C` |
| `PC_OUT` | `0F` |
| `IR_OUT` | `33FF` |
| `FLAGS_OUT` | `1` (Z=1, N=C=V=0) |

## Verify with the actual simulator

From the repository root, with Python 3 and Java installed:

```sh
python3 scripts/verify.py --jar /path/to/Digital.jar
```

The runner drives the actual circuit using Digital's native test engine and
checks the PC, current instruction, flags, registers, and memory at successive
steps. It also tests all seven component circuits. It does not substitute a
software CPU emulator for the circuit.

## Original ROM image

[`original-rom.hex`](original-rom.hex) preserves the 132 instruction words
that were embedded in the original project. Its purpose and expected output
were not documented, so it is preserved as an archival artifact rather than
used as the reproducible demo.
