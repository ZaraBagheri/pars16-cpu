#!/usr/bin/env python3
"""Validate Pars16 files and run the real Digital simulator's test engine.

No CPU emulator is used. Test vectors are applied to the actual .dig circuits in
a temporary directory, so the repository's schematics are never changed.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CIRCUITS = ROOT / "circuits"


def attributes(element):
    return {entry[0].text: entry[1] for entry in element.findall("elementAttributes/entry")}


def read_hex(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "v2.0 raw":
        raise ValueError(f"{path}: expected a Logisim/Digital 'v2.0 raw' header")
    words = [int(word, 16) for line in lines[1:] for word in line.split()]
    if not words or any(not 0 <= word <= 0xFFFF for word in words):
        raise ValueError(f"{path}: expected nonempty 16-bit hexadecimal words")
    return words


def program_rom(tree):
    for element in tree.findall("./visualElements/visualElement"):
        if element.findtext("elementName") == "ROM":
            attrs = attributes(element)
            if attrs.get("isProgramMemory") is not None and attrs["isProgramMemory"].text == "true":
                return attrs["Data"]
    raise ValueError("No instruction ROM found")


def structural_checks():
    paths = sorted(CIRCUITS.glob("*.dig"))
    if len(paths) != 8:
        raise ValueError(f"Expected eight circuit files, found {len(paths)}")
    for path in paths:
        tree = ET.parse(path)
        for element in tree.findall("./visualElements/visualElement"):
            name = element.findtext("elementName", "")
            if name.endswith(".dig") and not (path.parent / name).is_file():
                raise ValueError(f"{path.name}: missing subcircuit {name}")
    words = read_hex(ROOT / "examples/demo.hex")
    if len(words) != 16:
        raise ValueError("The documented demo must contain exactly 16 instructions")
    rom = program_rom(ET.parse(CIRCUITS / "Pars16.dig"))
    actual = [int(word.strip(), 16) for word in (rom.text or "").split(",") if word.strip()]
    if actual != words:
        raise ValueError("The embedded Pars16 instruction ROM differs from examples/demo.hex")
    read_hex(ROOT / "examples/original-rom.hex")
    print("Structure: eight valid XML circuits, complete dependencies, matching demo ROM", flush=True)
    return words


def test_file(path, label, header, rows):
    root = ET.Element("circuit")
    ET.SubElement(root, "version").text = "2"
    ET.SubElement(root, "attributes")
    elements = ET.SubElement(root, "visualElements")
    element = ET.SubElement(elements, "visualElement")
    ET.SubElement(element, "elementName").text = "Testcase"
    attrs = ET.SubElement(element, "elementAttributes")
    entry = ET.SubElement(attrs, "entry")
    ET.SubElement(entry, "string").text = "Label"
    ET.SubElement(entry, "string").text = label
    entry = ET.SubElement(attrs, "entry")
    ET.SubElement(entry, "string").text = "Testdata"
    data = ET.SubElement(entry, "testData")
    ET.SubElement(data, "dataString").text = header + "\n" + "\n".join(
        " ".join(str(value) for value in row) for row in rows
    )
    ET.SubElement(element, "pos", x="0", y="0")
    ET.SubElement(root, "wires")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def sign_extend(value, bits):
    return (value - (1 << bits) if value & (1 << (bits - 1)) else value) & 0xFFFF


def alu_rows():
    operands = [(0, 0), (1, 1), (5, 7), (7, 5), (0xFFFF, 1),
                (0x7FFF, 1), (0x8000, 1), (0x8000, 0xFFFF),
                (0x8000, 0x8000), (0xFFFF, 0xFFFF), (0xAAAA, 0x5555)]
    operands += [(0x8001, shift) for shift in range(16)]
    operands += [(0x8001, 0xFFF0), (0x8001, 0xFFF1), (0x8001, 0xFFFF)]
    for func in range(8):
        for a, b in operands:
            carry = overflow = 0
            if func == 0:
                result = (a + b) & 0xFFFF
                carry = int(a + b > 0xFFFF)
                overflow = int(bool((~(a ^ b) & (a ^ result)) & 0x8000))
            elif func == 1:
                result = (a - b) & 0xFFFF
                carry = int(a < b)  # This circuit uses C=borrow for subtraction.
                overflow = int(bool(((a ^ b) & (a ^ result)) & 0x8000))
            elif func == 2:
                result = a & b
            elif func == 3:
                result = a | b
            elif func == 4:
                result = a ^ b
            elif func == 5:
                result = (a << (b & 15)) & 0xFFFF
            elif func == 6:
                result = a >> (b & 15)
            else:
                result = 0
            yield a, b, func, result, int(result == 0), result >> 15, carry, overflow


def condition_rows():
    for cc in range(4):
        for flags in range(8):
            z, n, v = flags & 1, (flags >> 1) & 1, (flags >> 2) & 1
            yield cc, z, n, v, (1, z, n, v)[cc]


def extension_rows():
    for offset in range(1024):
        imm4, imm7 = offset & 15, offset & 127
        yield imm4, imm7, offset, sign_extend(imm4, 4), sign_extend(imm7, 7), sign_extend(offset, 10)


def control_rows():
    # Independently specified behavior: opcode, ALU, B select, A select, PC
    # select, writeback, link destination, flags capable, memory write, reg write.
    for opcode in range(7):
        yield opcode, opcode, 0, 0, 0, 0, 0, 1, 0, 1
    yield 7, 0, 1, 0, 0, 0, 0, 0, 0, 1
    yield 8, 0, 1, 0, 0, 1, 0, 0, 0, 1
    yield 9, 0, 1, 0, 0, 0, 0, 0, 1, 0
    yield 10, 0, 2, 1, 0, 0, 0, 0, 0, 1
    yield 11, 0, 0, 0, 0, 2, 0, 0, 0, 1
    yield 12, 0, 0, 0, 1, 0, 0, 0, 0, 0
    yield 13, 0, 0, 0, 1, 3, 1, 0, 0, 1
    yield 14, 0, 0, 0, 2, 0, 0, 0, 0, 0
    yield 15, 0, 0, 0, 0, 0, 0, 0, 0, 0


def flag_rows():
    # CLK RESET FLAG_WRITE Z_IN N_IN C_IN V_IN FLAGS_OUT Z_OUT N_OUT C_OUT V_OUT
    yield 0, 1, 0, 0, 0, 0, 0, "X", "X", "X", "X", "X"
    yield "C", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    for flags in range(16):
        bits = tuple((flags >> index) & 1 for index in range(4))
        yield ("C", 0, 1, *bits, flags, *bits)
        yield ("C", 0, 0, 1, 1, 1, 1, flags, *bits)
    yield "C", 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0


def register_rows():
    # CLK RESET WE WADDR WDATA RADDR1 RADDR2 DBG_RSEL RDATA1 RDATA2 DBG_ROUT
    values = [0] + [index * 0x1111 for index in range(1, 8)]
    yield 0, 1, 0, 0, 0, 0, 0, 0, "X", "X", "X"
    yield "C", 1, 0, 0, 0, 0, 0, 0, 0, 0, 0
    for register in range(1, 8):
        yield "C", 0, 1, register, values[register], register, register, register, values[register], values[register], values[register]
    # R0 remains zero despite an attempted write; WE=0 preserves R1.
    yield "C", 0, 1, 0, 0xFFFF, 0, 0, 0, 0, 0, 0
    yield "C", 0, 0, 1, 0xFFFF, 1, 1, 1, values[1], values[1], values[1]
    for r1 in range(8):
        for r2 in range(8):
            debug = (r1 + r2) % 8
            yield 0, 0, 0, 0, 0, r1, r2, debug, values[r1], values[r2], values[debug]
    yield "C", 1, 1, 1, 0xFFFF, 1, 7, 4, 0, 0, 0
    for register in range(8):
        yield 0, 0, 0, 0, 0, register, register, register, 0, 0, 0


def memory_rows():
    # CLK ADDR WDATA MEM_WRITE MADDR_DBG RDATA DBG_MOUT
    values = [(0, 0x1234), (1, 0xABCD), (0x7FFF, 0x55AA), (0x8000, 0xAA55), (0xFFFF, 0xFFFF)]
    yield 0, 0, 0, 0, 0, "X", "X"
    for address, value in values:
        yield "C", address, value, 1, address, value, value
    for address, value in values:
        for debug_address, debug_value in values:
            yield 0, address, 0, 0, debug_address, value, debug_value
    yield "C", 0, 0xFFFF, 0, 1, 0x1234, 0xABCD


def cpu_rows(words):
    # CLK RESET DBG_EN DBG_RSEL DBG_MADDR PC_OUT IR_OUT FLAGS_OUT DBG_ROUT DBG_MOUT
    yield 0, 1, 0, 0, 0, "X", "X", "X", 0, "X"
    yield "C", 1, 0, 0, 0, 0, words[0], 0, 0, "X"
    # Each tuple specifies the expected state after one executed instruction.
    checkpoints = [
        (1, 0, 1, 5, "X"), (2, 0, 2, 7, "X"), (3, 0, 3, 12, "X"),
        (4, 0, 3, 12, 12), (5, 0, 4, 12, 12), (6, 1, 5, 0, 12),
        (7, 1, 6, 1, 12), (8, 1, 6, 1, 12), (10, 1, 6, 1, 12),
        (13, 1, 7, 11, 12), (14, 1, 6, 2, 12), (11, 1, 7, 11, 12),
        (15, 1, 6, 2, 12), (15, 1, 6, 2, 12),
    ]
    for pc, flags, register, value, memory in checkpoints:
        yield "C", 0, 0, register, 0, pc, words[pc], flags, value, memory
    for register, value in enumerate([0, 5, 7, 12, 12, 0, 2, 11]):
        yield 0, 0, 0, register, 0, 15, words[15], 1, value, 12
    # A synchronous reset restores registers/flags/PC. Data RAM is retained.
    yield "C", 1, 0, 6, 0, 0, words[0], 0, 0, 12


def suites(words):
    return [
        ("ALU", "Arithmetic, logic, shift and flag boundary cases", "A B ALU_FUNC RESULT Z N C V", alu_rows()),
        ("ConditionEvaluator", "All condition and input flag combinations", "CC Z N V COND_MET", condition_rows()),
        ("SignExtend", "Exhaustive immediate and offset sign extension", "IMM4_IN IMM7_IN OFFSET10_IN IMM4_EXT IMM7_EXT OFFSET10_EXT", extension_rows()),
        ("ControlUnit", "All sixteen instruction control words", "OPCODE ALU_FUNC ALU_B_SEL ALU_A_SEL PC_SEL WB_SEL REG_DST FLAG_CAPABLE MEM_WRITE REG_WRITE", control_rows()),
        ("FlagRegister", "Flag writes, holds and reset", "CLK RESET FLAG_WRITE Z_IN N_IN C_IN V_IN FLAGS_OUT Z_OUT N_OUT C_OUT V_OUT", flag_rows()),
        ("RegisterFile", "Register ports, zero register, write enable and reset", "CLK RESET WE WADDR WDATA RADDR1 RADDR2 DBG_RSEL RDATA1 RDATA2 DBG_ROUT", register_rows()),
        ("DataMemory", "Memory writes, held values and independent debug reads", "CLK ADDR WDATA MEM_WRITE MADDR_DBG RDATA DBG_MOUT", memory_rows()),
        ("Pars16", "CPU demo: arithmetic, memory, conditions, branches and subroutine", "CLK RESET DBG_EN DBG_RSEL DBG_MADDR PC_OUT IR_OUT FLAGS_OUT DBG_ROUT DBG_MOUT", cpu_rows(words)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", default=os.environ.get("DIGITAL_JAR"), help="Path to Digital.jar (or set DIGITAL_JAR)")
    parser.add_argument("--java", default=os.environ.get("JAVA", "java"), help="Java executable (default: JAVA or java)")
    parser.add_argument("--static", action="store_true", help="Check files only; does not verify circuit behavior")
    args = parser.parse_args()
    try:
        words = structural_checks()
        if args.static:
            print("Static checks passed. Simulation was not run.")
            return 0
        if not args.jar or not Path(args.jar).is_file():
            parser.error("supply --jar /path/to/Digital.jar or set DIGITAL_JAR")
        jar = str(Path(args.jar).resolve())
        rows_checked = 0
        with tempfile.TemporaryDirectory(prefix="pars16-tests-") as directory:
            work = Path(directory)
            for circuit in CIRCUITS.glob("*.dig"):
                shutil.copy2(circuit, work / circuit.name)
            for name, label, header, rows in suites(words):
                rows = list(rows)
                rows_checked += len(rows)
                tests = work / (name + "-tests.dig")
                test_file(tests, label, header, rows)
                print(f"\n{name}: {len(rows)} test rows", flush=True)
                subprocess.run([args.java, "-Djava.awt.headless=true", "-cp", jar, "CLI", "test", "-circ", str(work / (name + ".dig")), "-tests", str(tests), "-verbose"], check=True)
        print(f"\nPASS: eight circuit suites, {rows_checked} native Digital test rows.")
        return 0
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
