#!/usr/bin/env python3

import pexpect

from typing import Dict, Any

import argparse
import json
import sys


def setup(process: pexpect.spawn, params: Dict[str, Any]):
    # Whether we want to import from another control file
    process.expect("THEN ENTER ITS LOCATION/NAME OR OTHERWISE HIT >return<.\r\n\r\n")
    process.sendline("")
    process.expect("TO REPEAT DEFINITION OF DEFAULT INPUT FILE")
    process.sendline(params.get("title", ""))


def configure_geometry(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"SPECIFICATION OF MOLECULAR GEOMETRY \(\s*#ATOMS=(\d+)\s*SYMMETRY=([a-zA-Z_0-9]+)\s+\)"
    end_of_prompt = "OF THAT COMMAND MAY BE GIVEN"
    process.expect(headline)
    process.expect(end_of_prompt)
    process.sendline("a {}".format(params["geometry"]))

    process.expect(headline)
    nAtoms = int(process.match.group(1))
    if nAtoms == 0:
        raise RuntimeError(
            "Failed at adding geometry '{}': no atoms were added".format(
                params["geometry"]
            )
        )

    process.expect(end_of_prompt)

    if params.get("use_redundant_coords", True):
        process.sendline("ired")
        process.expect(end_of_prompt)
    if params.get("detect_symmetry", True):
        process.sendline("desy")
        process.expect(headline)
        sym = process.match.group(2).decode("utf-8")
        print("Detected symmetry: {}".format(sym))
        process.expect(end_of_prompt)

    process.sendline("*")


def configure_basis_set(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"ATOMIC ATTRIBUTE DEFINITION MENU\s*\(\s*#atoms=(\d+)\s*#bas=(\d+)\s*#ecp=(\d+)\s*\)"
    end_of_prompt = r"GOBACK=& \(TO GEOMETRY MENU !\)\r\n"
    basis_set_not_found = r"THERE ARE NO DATA SETS CATALOGUED IN FILE\s*\r\n(.+)\r\n\s*CORRESPONDING TO NICKNAME\s*([^\n]+)\r\n"

    process.expect(headline)
    process.expect(end_of_prompt)

    if not "basis_set" in params:
        # If no basis set was specified by the user, use TM's defaults
        print("Using default basis set(s) as proposed by TurboMole")
        process.sendline("*")

    basis_info: Dict[str, Any] = params["basis_set"]
    if len(basis_info) == 0:
        raise RuntimeError("'basis_set' object must not be empty!")

    # Specify basis sets
    for group in basis_info:
        basis_set = basis_info[group]

        if group != "all" and group.isalpha() and len(group) <= 2:
            # We assume this is an element label -> wrap in quotes
            group = '"{}"'.format(group)

        process.sendline("b {} {}".format(group, basis_set))
        idx = process.expect([basis_set_not_found, end_of_prompt])
        if idx == 0:
            basis_set_nick = process.match.group(2).decode("utf-8").strip()
            basis_set_file = process.match.group(1).decode("utf-8").strip()
            raise RuntimeError(
                "Invalid basis '{}' - check '{}' for available basis sets".format(
                    basis_set_nick, basis_set_file
                )
            )

    if not params.get("use_ecp", True):
        process.sendline("ecprm all")
        process.expect(headline)
        nECPs = int(process.match.group(3))
        if nECPs != 0:
            raise RuntimeError("Failed at removing ECPs")
        process.expect(end_of_prompt)

    process.sendline("")
    process.expect(headline)
    nAtoms = int(process.match.group(1))
    nBasisSets = int(process.match.group(2))

    if nAtoms > nBasisSets:
        raise RuntimeError("Not all atoms have an associated basis set")

    process.expect(end_of_prompt)
    process.sendline("*")


def configure_occupation(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"OCCUPATION NUMBER & MOLECULAR ORBITAL DEFINITION MENU"
    end_of_prompt = r"FOR EXPLANATIONS APPEND A QUESTION MARK \(\?\) TO ANY COMMAND"
    default_prompt = r"DO YOU WANT THE DEFAULT.+\r\n|DO YOU WANT THESE\s*?.+\r\n"
    charge_prompt = r"ENTER THE MOLECULAR CHARGE.+\r\n"
    occupation_prompt = r"DO YOU ACCEPT THIS OCCUPATION\s*\?"
    nat_orb_prompt = r"DO YOU REALLY WANT TO WRITE OUT NATURAL ORBITALS\s\?.+\r\n"

    process.expect(headline)
    process.expect(end_of_prompt)

    process.sendline("eht")

    cont = True
    while cont:
        idx = process.expect(
            [default_prompt, charge_prompt, occupation_prompt, nat_orb_prompt]
        )
        if idx == 0:
            # Always accept defaults
            process.sendline("y")
        elif idx == 1:
            process.sendline("{}".format(params.get("charge", 0)))
        elif idx == 2:
            # Always accept the produced occupation
            process.sendline("y")
        elif idx == 3:
            process.sendline(
                "{}".format("y" if params.get("write_natural_orbitals", False) else "n")
            )
            cont = False

    # Note: Using eht automatically terminates the occ menu


def configuere_calc_params(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"GENERAL MENU : SELECT YOUR TOPIC"
    end_of_prompt = r"\* or q\s*: END OF DEFINE SESSION"

    process.expect(headline)
    process.expect(end_of_prompt)

    if not "calculation" in params:
        print("Using default calculation parameter")
        process.sendline("*")
        return

    calc_params = params["calculation"]
    if len(calc_params) == 0:
        raise RuntimeError("calculation object must not be empty")

    # Generic option instructions to cover all cases for which we don't have pre-defined options
    # The syntax is a simple
    # first > second > third > value
    # where the different parts (separated by ">") will be entered one after another
    if "generic" in calc_params:
        for instruction in calc_params["generic"]:
            parts = instruction.split(">")
            parts = [x.strip() for x in parts]
            for currentPart in parts:
                process.sendline(currentPart)

            # Ensure we arrive back in the main menu
            for _ in range(max(0, len(parts) - 1)):
                # We're relying on being able to get a menu back up by pressing enter
                process.sendline("")

            process.expect(headline)
            process.expect(end_of_prompt)

    process.sendline("*")


def run_define(params: Dict[str, Any], debug: bool = False, timeout: int = 10):
    process = pexpect.spawn("define")
    process.timeout = timeout
    if debug:
        process.logfile = sys.stdout.buffer

    setup(process, params)
    configure_geometry(process, params)
    configure_basis_set(process, params)
    configure_occupation(process, params)
    configuere_calc_params(process, params)


def main():
    parser = argparse.ArgumentParser(
        description="Run define with a set of pre-defined parameters in order to prepare a TurboMole computation"
    )
    parser.add_argument(
        "--parameter",
        help="Path to the parameter file",
        metavar="PATH",
        default="calculation_parameter.json",
    )
    parser.add_argument(
        "--debug",
        help="Print extra output useful for debugging when things don't go as expected",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--timeout",
        help="Maximum time to wait on the expected output from define",
        default=10,
        type=int,
    )
    parser.add_argument(
        "--dont-execute",
        help=argparse.SUPPRESS,
        default=False,
        action="store_true",
    )

    args = parser.parse_args()

    if args.dont_execute:
        return

    with open(args.parameter, "r") as param_file:
        parameter = json.load(param_file)

    run_define(parameter, debug=args.debug, timeout=args.timeout)


if __name__ == "__main__":
    main()
