"""
gen_sample_data.py — Generate sample PDF and TXT notes for demo and testing.

Usage:
  python scripts/gen_sample_data.py [--output-dir ./sample_notes]

Creates:
  - biology_notes.txt
  - chemistry_notes.txt
  - adversarial_refusal_test.txt (facts NOT in the other files)
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

BIOLOGY_NOTES = textwrap.dedent("""\
    Biology Study Notes — Chapter 3
    ================================

    Photosynthesis
    --------------
    Photosynthesis is the process by which plants use sunlight, water, and carbon dioxide
    to produce glucose and oxygen. The chemical equation is:
    6CO2 + 6H2O + light energy → C6H12O6 + 6O2

    The process occurs in the chloroplasts, specifically in the thylakoid membranes (light
    reactions) and the stroma (Calvin cycle / dark reactions).

    Key pigment: chlorophyll a absorbs light mostly in the blue-violet and red wavelengths.

    Cell Division — Mitosis
    -----------------------
    Mitosis is the division of a eukaryotic cell's nucleus into two identical daughter nuclei.
    The stages are: Prophase, Metaphase, Anaphase, Telophase, and Cytokinesis (PMATC).

    - Prophase: chromosomes condense; spindle fibres form.
    - Metaphase: chromosomes align at the cell equator (metaphase plate).
    - Anaphase: sister chromatids are pulled to opposite poles.
    - Telophase: nuclear envelopes reform; chromosomes decondense.
    - Cytokinesis: cytoplasm divides, producing two daughter cells.

    DNA Structure
    -------------
    DNA is a double helix composed of two antiparallel strands of nucleotides.
    Each nucleotide contains a deoxyribose sugar, a phosphate group, and a nitrogenous base.
    Base pairing: Adenine (A) pairs with Thymine (T); Guanine (G) pairs with Cytosine (C).

    The human genome contains approximately 3 billion base pairs.
""")

CHEMISTRY_NOTES = textwrap.dedent("""\
    Chemistry Notes — Atomic Structure & Bonding
    =============================================

    Atomic Structure
    ----------------
    An atom consists of a nucleus (protons + neutrons) surrounded by electrons in shells.
    Atomic number = number of protons (defines the element).
    Mass number = protons + neutrons.

    Isotopes are atoms of the same element with different numbers of neutrons.
    Example: Carbon-12 (6p, 6n) and Carbon-14 (6p, 8n).

    Chemical Bonding
    ----------------
    Ionic bonds form by transfer of electrons from a metal to a non-metal.
    Example: NaCl — sodium donates one electron to chlorine.

    Covalent bonds form by sharing of electron pairs between non-metals.
    Example: Water (H2O) — oxygen shares electrons with two hydrogen atoms.

    Water has a bent molecular geometry due to the two lone pairs on oxygen,
    giving it a bond angle of approximately 104.5 degrees.

    Periodic Table Trends
    ---------------------
    Atomic radius decreases across a period (left to right) due to increasing nuclear charge.
    Electronegativity increases across a period and decreases down a group.
    Ionisation energy generally increases across a period.

    Moles and Stoichiometry
    -----------------------
    One mole of a substance contains 6.022 × 10^23 particles (Avogadro's number).
    Molar mass is the mass of one mole of a substance in grams/mol.

    Ideal Gas Law: PV = nRT
    where P = pressure, V = volume, n = moles, R = 8.314 J/mol·K, T = temperature in Kelvin.
""")

ADVERSARIAL_NOTES = textwrap.dedent("""\
    ADVERSARIAL TEST FILE — Contents intentionally minimal.

    This file contains only one fact:
    The speed of light in a vacuum is approximately 3 × 10^8 metres per second.

    Any question about biology, chemistry, history, mathematics, or any other subject
    should be refused because it is NOT found in this file.
""")


def write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"  Written: {path} ({len(content)} chars)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample notes for AskMyNotes demo.")
    parser.add_argument("--output-dir", default="./sample_notes", help="Output directory")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating sample notes in {out.resolve()}...")
    write_file(out / "biology_notes.txt", BIOLOGY_NOTES)
    write_file(out / "chemistry_notes.txt", CHEMISTRY_NOTES)
    write_file(out / "adversarial_refusal_test.txt", ADVERSARIAL_NOTES)
    print("\nDone. Upload these files to the demo subjects to test the system.")
    print("Adversarial queries to test refusal:")
    print("  - Subject: adversarial  → Q: 'What is photosynthesis?' → expect refusal")
    print("  - Subject: adversarial  → Q: 'What is the speed of light?' → expect answer")


if __name__ == "__main__":
    main()
