# Pars16 instruction set

This reference describes the wiring and control ROM in [Pars16.dig](../circuits/Pars16.dig). The mnemonic names below are descriptive notation for the circuit's operations; the project does not include an assembler.

## Programmer-visible state

| State | Implementation |
| --- | --- |
| Data and instruction width | 16 bits |
| Registers | `R0`–`R7`; `R0` always reads zero and ignores writes; `R1`–`R7` are writable |
| Program counter | 8 bits; addresses 256 instruction words |
| Instruction memory | Separate 256 × 16-bit ROM |
| Data memory | Separate 65,536 × 16-bit RAM; word-addressed |
| Status flags | `Z` (zero), `N` (negative), `C` (carry/borrow), `V` (signed overflow) |
| Link register | `R7`, written by `JAL` |

Arithmetic results and data addresses wrap modulo 65,536. Instructions normally advance the PC by one word. Register, flag, PC, and RAM writes occur on rising clock edges.

## Instruction encoding

Every instruction has a two-bit condition field and a four-bit opcode:

```text
 15 14  13          10  9                                  0
+------+--------------+------------------------------------+
|  CC  |    opcode    |       operation-specific fields    |
+------+--------------+------------------------------------+
```

The remaining fields depend on the operation:

```text
Register ALU: CC[15:14] opcode[13:10] d[9:7] a[6:4] b[3:1] S[0]
ADDI/LD/ST:   CC[15:14] opcode[13:10] d[9:7] a[6:4] imm4[3:0]
LI/LUI:      CC[15:14] opcode[13:10] d[9:7] imm7[6:0]
B/JAL:       CC[15:14] opcode[13:10] offset10[9:0]
JR:          CC[15:14] opcode[13:10] source[9:7] unused[6:0]
NOP:         CC[15:14] opcode[13:10] unused[9:0]
```

Here, `d` is the destination register (or the stored register for `ST`), `a` and `b` select source registers, and `S` requests a flag update. Unused fields can be zero. For immediate instructions, bit 0 is part of the immediate, not an independent flag-write request.

## Operations

The table assumes the condition is satisfied and `DBG_EN = 0`. `sext` means sign extension to 16 bits, `M[x]` is a 16-bit data-memory word, and `next` is `(PC + 1) mod 256`.

| Opcode | Illustrative syntax | Effect |
| --- | --- | --- |
| `0x0` | `ADD R[d], R[a], R[b]` | `R[d] ← R[a] + R[b]` |
| `0x1` | `SUB R[d], R[a], R[b]` | `R[d] ← R[a] - R[b]` |
| `0x2` | `AND R[d], R[a], R[b]` | Bitwise AND |
| `0x3` | `OR R[d], R[a], R[b]` | Bitwise OR |
| `0x4` | `XOR R[d], R[a], R[b]` | Bitwise XOR |
| `0x5` | `SHL R[d], R[a], R[b]` | Logical left shift by `R[b] & 0xF` |
| `0x6` | `SHR R[d], R[a], R[b]` | Logical right shift by `R[b] & 0xF` |
| `0x7` | `ADDI R[d], R[a], imm4` | `R[d] ← R[a] + sext(imm4)` |
| `0x8` | `LD R[d], [R[a] + imm4]` | `R[d] ← M[R[a] + sext(imm4)]` |
| `0x9` | `ST R[d], [R[a] + imm4]` | `M[R[a] + sext(imm4)] ← R[d]` |
| `0xA` | `LI R[d], imm7` | `R[d] ← sext(imm7)` |
| `0xB` | `LUI R[d], imm7` | `R[d] ← (imm7 & 0x7F) << 9`; low nine bits are zero |
| `0xC` | `B offset10` | `PC ← (next + sext(offset10)) mod 256` |
| `0xD` | `JAL offset10` | `R7 ← next`, zero-extended to 16 bits; branch as above |
| `0xE` | `JR R[source]` | `PC ← R[source] & 0xFF`; source is encoded in bits 9:7 |
| `0xF` | `NOP` | No register, flag, or memory write; advance to `next` |

Opcodes `0x0`–`0x6` support optional flag updates. In illustrative syntax, `ADD.S` means `ADD` with `S = 1`; without `.S`, use `S = 0`. Other opcodes preserve the flags, including `ADDI`, loads, and immediate loads.

The final, unpopulated control-ROM entry reads as zero, giving opcode `0xF` its no-operation behavior. There is no halt instruction. An unconditional `B -1` repeatedly executes its own address.

## Conditions and flags

The condition applies to every instruction class, including register writes, stores, flag updates, branches, and calls. It uses the previously stored flags. When the condition fails, the instruction has no architectural write effects and the PC advances to `next`.

| `CC` | Condition | Illustrative suffix |
| --- | --- | --- |
| `00` | Always | No suffix |
| `01` | `Z = 1` | `.Z` |
| `10` | `N = 1` | `.N` |
| `11` | `V = 1` | `.V` |

For example, `LI.Z R6, 1` encodes `CC = 01`; `B.Z +1` skips the next instruction when `Z` is set. These names are documentation notation, not assembler syntax accepted by a bundled tool.

There is no direct carry condition, inverted condition, or combined signed-comparison condition. In particular, the `.N` condition checks the negative flag alone, rather than `N XOR V`.

| Flag | Calculation when flags are updated |
| --- | --- |
| `Z` | One when the 16-bit result is zero |
| `N` | Bit 15 of the result |
| `C`, addition | Carry out of the 16-bit addition |
| `C`, subtraction | Borrow: one when unsigned `R[a] < R[b]` |
| `V`, addition | One when equal-sign operands produce the opposite-sign result |
| `V`, subtraction | One when different-sign operands produce a result whose sign differs from `R[a]` |
| `C` and `V`, logic/shifts | Both zero; shifted-out bits are not retained in `C` |

`FLAGS_OUT[3:0]` is ordered `V C N Z`. All four flags update together only when `COND_MET AND S AND FLAG_CAPABLE` is true. Writing an ALU result to `R0` discards that result but can still update flags, making `SUB.S R0, R[a], R[b]` useful as a comparison.

## Immediate values and PC wrapping

| Field | Interpretation |
| --- | --- |
| `imm4` | Signed two's complement, −8 through +7 |
| `imm7` for `LI` | Signed two's complement, −64 through +63 |
| `imm7` for `LUI` | Raw seven-bit pattern placed in bits 15:9 |
| `offset10` | Signed two's complement, −512 through +511 |

For a negative immediate, encode its two's-complement bit pattern in the corresponding field. For example, `imm4 = -1` is `0xF`, and `offset10 = -1` is `0x3FF`.

Although relative offsets have ten bits, the destination PC keeps only the low eight bits. Offsets that differ by 256 therefore reach the same address. The sequential PC wraps from `0xFF` to `0x00`, and a `JAL` at `0xFF` stores `0x0000` in `R7`. Register jumps similarly ignore the upper eight bits of the source register.

## Control-ROM encoding

[ControlUnit.dig](../circuits/ControlUnit.dig) maps the four-bit opcode to a 16-bit control word:

| Control-word bits | Signal |
| --- | --- |
| 15 | `REG_WRITE` |
| 14 | `MEM_WRITE` |
| 13 | `FLAG_CAPABLE` |
| 12 | `REG_DST`: `0` = instruction bits 9:7; `1` = `R7` |
| 11:10 | `WB_SEL`: `0` = ALU; `1` = data memory; `2` = LUI; `3` = zero-extended `next` |
| 9:8 | `PC_SEL`: `0` = sequential; `1` = relative; `2` = register; `3` = sequential |
| 7 | `ALU_A_SEL`: `0` = first register operand; `1` = zero |
| 6:5 | `ALU_B_SEL`: `0` = second register operand; `1` = signed `imm4`; `2` = signed `imm7`; `3` = zero |
| 4:2 | `ALU_FUNC`: ADD, SUB, AND, OR, XOR, SHL, SHR, zero for values 0–7 |
| 1:0 | Unused |

The words for opcodes `0x0`–`0xF` are:

```text
A000 A004 A008 A00C A010 A014 A018 8020
8420 4020 80C0 8800 0100 9D00 0200 0000
```

## Reset and debug behavior

`RESET` is synchronous: assert it before a rising clock edge to clear the PC, writable registers, and flags. It does not clear data memory. In the current circuit, reset also does not suppress the memory write-enable path; clocking reset while an enabled store is selected can still write to RAM.

`PC_OUT` exposes the current PC. `IR_OUT` exposes the instruction ROM output at that address, rather than a separately latched instruction register. After a clock step, it shows the instruction selected by the updated PC.

`DBG_RSEL` selects `DBG_ROUT` through a dedicated register-file read port. `DBG_MADDR` selects `DBG_MOUT` through a separate RAM read port. These reads do not require `DBG_EN`.

Keep `DBG_EN = 0` during normal execution. In the current wiring, asserting it substitutes `DBG_RSEL` for the second execution read address as well; this changes register-ALU operands and store data. It does not pause the clock or freeze the processor. To inspect state without changing execution, stop toggling `CLK` and use the dedicated debug outputs.

The sign-extension and memory-edge descriptions use the behavior of Digital v0.31's [BitExtender](https://github.com/hneemann/Digital/blob/v0.31/src/main/java/de/neemann/digital/core/arithmetic/BitExtender.java) and [RAMDualAccess](https://github.com/hneemann/Digital/blob/v0.31/src/main/java/de/neemann/digital/core/memory/RAMDualAccess.java) components.
