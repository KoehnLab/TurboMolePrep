#!/usr/bin/env python3

import pexpect

from typing import Dict, Any, Optional

import argparse
import json
import sys
import subprocess
import os

default_key = "-DeFaUlT-"
array_type_key = "-ArRaYtYpE-"

dft_params = {
    "functional": str,
    "grid": [str, int],
    "dispersion_correction": str,
}
molecule_options = {
    "geometry": str,
    "use_internal_coords": bool,
    "detect_symmetry": bool,
    "charge": int,
    "isotopes": {
        default_key: [int, {"nucleon_count": int, "gyromagnetic_ratio": float}]
    },
}
basis_set_options = {default_key: str, "use_ecp": bool}
x2c_options = {"enable": bool, "local_approx": bool, "picture_change_corr": bool}

param_types = {
    "title": str,
    "molecule": [str, molecule_options],
    "write_natural_orbitals": bool,
    "basis_set": [str, basis_set_options],
    "calculation": {
        "dft": [str, dft_params],
        "finite_nucleus": bool,
        "max_scf_iterations": int,
        "x2c": [bool, x2c_options],
        "generic": {array_type_key: str},
        "ri": [str, {"type": str, "multipole_acceleration": bool}],
    },
}


def optional_match_group(process: pexpect.spawn, group: int) -> Optional[str]:
    match = process.match.group(group)  # type: ignore

    if match is not None and type(match) is bytes:
        match = match.decode("utf-8")

    return match


def match_group(process: pexpect.spawn, group: int) -> str:
    match = optional_match_group(process, group)
    assert match is not None
    return match


def validate_parameter(
    params: Dict[str, Any], sub_level: Optional[str] = None, scheme=param_types
):
    for key in params:
        if type(key) is not str:
            raise RuntimeError(
                "All keys must be strings, but '{}' is '{}'".format(key, key)
            )

        if not key in scheme:
            if default_key in scheme:
                allowed = scheme[default_key]
                if not type(allowed) is list:
                    allowed = [allowed]
                if type(params[key]) is dict and any(type(x) is dict for x in allowed):
                    validate_parameter(
                        params[key],
                        sub_level=key,
                        scheme=[x for x in scheme[default_key] if type(x) is dict][0],
                    )
                elif type(params[key]) not in allowed:
                    raise RuntimeError(
                        "Expected type of value of '{}' to be one of '{}'".format(
                            key,
                            ", ".join(
                                [
                                    x.__name__ if type(x) is not dict else str(x)
                                    for x in allowed
                                ]
                            ),
                        )
                    )
                continue
            if sub_level is None:
                raise RuntimeError("Unknown top-level key '{}'".format(key))
            else:
                raise RuntimeError(
                    "Unknown key '{}' for group '{}'".format(key, sub_level)
                )

        if type(scheme[key]) is type:
            if type(params[key]) is not scheme[key]:
                raise RuntimeError(
                    "Expected value of '{}' to be of type '{}'".format(
                        key, scheme[key].__name__
                    )
                )
        elif type(scheme[key]) is list:
            if not type(params[key]) in scheme[key]:
                if all(type(x) == type for x in scheme[key]):
                    raise RuntimeError(
                        "Expected the type of the value of '{}' to be one of '{}', but got '{}'".format(
                            key,
                            ", ".join([x.__name__ for x in scheme[key]]),
                            type(params[key]).__name__,
                        )
                    )
                else:
                    non_type_entries = [x for x in scheme[key] if type(x) is not type]
                    assert len(non_type_entries) == 1
                    assert type(non_type_entries[0]) == dict

                    if type(params[key]) is not dict:
                        raise RuntimeError(
                            "Expected the type of the value of '{}' to be one of '{}' or a sub-object, but got '{}'".format(
                                key,
                                ", ".join(
                                    x.__name__ for x in scheme[key] if type(x) is type
                                ),
                                type(params[key]).__name__,
                            )
                        )

                    validate_parameter(
                        params=params[key], sub_level=key, scheme=non_type_entries[0]
                    )
        elif type(scheme[key]) is dict:
            if array_type_key in scheme[key]:
                # The parameter at key is expected to be a list of expected_type
                expected_type: type = scheme[key][array_type_key]
                if type(params[key]) is not list:
                    raise RuntimeError(
                        "'{}' is expected to be a list of '{}'s".format(
                            key, expected_type.__name__
                        )
                    )

                for value in params[key]:
                    if type(value) is not expected_type:
                        raise RuntimeError(
                            "'{}' is expected to be a list of '{}'s, but '{}' is of type '{}'".format(
                                key, expected_type.__name__, value, type(value).__name__
                            )
                        )
            else:
                # The parameter at key is expected to be a sub-object (dict)
                if type(params[key]) is not dict:
                    raise RuntimeError("'{}' is expected to be a sub-object (dict)")

                validate_parameter(
                    params=params[key], sub_level=key, scheme=scheme[key]
                )
        else:
            raise RuntimeError(
                "Unhandled type '{}' in scheme specification for '{}'".format(
                    type(scheme[key]).__name__
                ),
                key,
            )


def setup(process: pexpect.spawn, params: Dict[str, Any]):
    # Whether we want to import from another control file
    process.expect("THEN ENTER ITS LOCATION/NAME OR OTHERWISE HIT >return<.\r\n\r\n")
    process.sendline("")
    process.expect("TO REPEAT DEFINITION OF DEFAULT INPUT FILE")
    process.sendline(params.get("title", ""))


def configure_geometry(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"SPECIFICATION OF MOLECULAR GEOMETRY \(\s*#ATOMS=(\d+)\s*SYMMETRY=([a-zA-Z_0-9]+)\s+\)"
    end_of_prompt = "OF THAT COMMAND MAY BE GIVEN"
    internal_coord_prompt = (
        r"IF YOU DO NOT WANT TO USE INTERNAL COORDINATES ENTER\s*no\r\n"
    )

    process.expect(headline)
    process.expect(end_of_prompt)
    process.sendline("a {}".format(params["molecule"]["geometry"]))

    process.expect(headline)
    nAtoms = int(match_group(process, 1))
    if nAtoms == 0:
        raise RuntimeError(
            "Failed at adding geometry '{}': no atoms were added".format(
                params["molecule"]["geometry"]
            )
        )

    process.expect(end_of_prompt)

    if params["molecule"].get("detect_symmetry", True):
        process.sendline("desy 0.1")
        process.expect(headline)
        sym = match_group(process, 2)
        print("Detected symmetry: {}".format(sym))
        process.expect(end_of_prompt)

    use_interals = params["molecule"].get("use_internal_coords", True)

    if use_interals:
        process.sendline("ired")
        process.expect(end_of_prompt)

    process.sendline("*")

    if not use_interals:
        # Confirm that we indeed do not want internal coordinates
        process.expect(internal_coord_prompt)
        process.sendline("no")


def basis_set_group_sort_key(expr: str) -> str:
    if expr.lower() == "all":
        return "0_{}".format(expr)
    elif expr[0].isalpha():
        return "1_{}".format(expr)
    else:
        return "2_{}".format(expr)


def configure_basis_set(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"ATOMIC ATTRIBUTE DEFINITION MENU\s*\(\s*#atoms=(\d+)\s*#bas=(\d+)\s*#ecp=(\d+)\s*\)"
    end_of_prompt = r"GOBACK=& \(TO GEOMETRY MENU !\)\r\n"
    basis_set_not_found = r"THERE ARE NO DATA SETS CATALOGUED IN FILE\s*\r\n(.+)\r\n\s*CORRESPONDING TO NICKNAME\s*([^\n]+)\r\n"
    isotope_header = r"ENTER A SET OF ATOMS TO WHICH YOU WANT TO ASSIGN ISOTOPES"
    isotope_no_gyrmag = r"NO GYROMAGNETIC RATIO WAS FOUND IN THE DATABASE"
    isotope_assigned = r"SUPPLYING ISOTOPES TO"

    process.expect(headline)
    process.expect(end_of_prompt)

    if "basis_set" in params:
        basis_info: Dict[str, Any] = params["basis_set"]

        if len(basis_info) == 0:
            raise RuntimeError("'basis_set' object must not be empty!")

        # Specify basis sets
        # Always process from least specific group to most specific group
        # That means (for us) "all" before element labels before element indices
        groups = list(basis_info.keys())
        groups.sort(key=basis_set_group_sort_key)

        for group in groups:
            basis_set = basis_info[group]

            if group.isalpha():
                group = group.lower()

            if group != "all" and group.isalpha() and len(group) <= 2:
                # We assume this is an element label -> wrap in quotes
                group = '"{}"'.format(group)

            process.sendline("b {} {}".format(group, basis_set))
            idx = process.expect([basis_set_not_found, end_of_prompt])
            if idx == 0:
                basis_set_nick = match_group(process, 2).strip()
                basis_set_file = match_group(process, 1).strip()
                raise RuntimeError(
                    "Invalid basis '{}' - check '{}' for available basis sets".format(
                        basis_set_nick, basis_set_file
                    )
                )

        if not basis_info.get("use_ecp", True):
            process.sendline("ecprm all")
            process.expect(headline)
            nECPs = int(match_group(process, 3))
            if nECPs != 0:
                raise RuntimeError("Failed at removing ECPs")
            process.expect(end_of_prompt)

        process.sendline("")
        process.expect(headline)
        nAtoms = int(match_group(process, 1))
        nBasisSets = int(match_group(process, 2))

        if nAtoms > nBasisSets:
            raise RuntimeError("Not all atoms have an associated basis set")

        process.expect(end_of_prompt)
    else:
        # If no basis set was specified by the user, use TM's defaults
        print("Using default basis set(s) as proposed by TurboMole")

    if "isotopes" in params["molecule"]:
        process.sendline("iso")
        for element in params["molecule"]["isotopes"]:
            process.expect(isotope_header)
            nucleon_count = params["molecule"]["isotopes"][element]["nucleon_count"]
            gyromagnetic_ratio = params["molecule"]["isotopes"][element].get(
                "gyromagnetic_ratio", None
            )

            process.sendline('"{}" {}'.format(element.lower(), nucleon_count))
            process.expect(isotope_assigned)
            index = process.expect([isotope_no_gyrmag, pexpect.TIMEOUT], timeout=1)

            if index == 0:
                if gyromagnetic_ratio is None:
                    process.sendline("")
                    print(
                        "Unknown or zero gyromagnetic ratio for {}{} - ignoring".format(
                            nucleon_count, element
                        )
                    )
                else:
                    process.sendline(str(gyromagnetic_ratio))
            else:
                assert index == 1
                if gyromagnetic_ratio is not None:
                    raise RuntimeError(
                        "Define doesn't allow assignment of gyromagnetic ratio for {}{}".format(
                            nucleon_count, element
                        )
                    )

            # Re-enter isotope assignment menu
            process.sendline("iso")

        # Exit isotope menu
        process.sendline("")
        process.expect(end_of_prompt)

    process.sendline("*")


def configure_occupation(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"OCCUPATION NUMBER & MOLECULAR ORBITAL DEFINITION MENU"
    end_of_prompt = r"FOR EXPLANATIONS APPEND A QUESTION MARK \(\?\) TO ANY COMMAND"
    default_prompt = r"DO YOU WANT THE DEFAULT.+\r\n|DO YOU WANT THESE\s*?.+\r\n"
    charge_prompt = r"ENTER THE MOLECULAR CHARGE.+\r\n"
    occupation_prompt = r"DO YOU ACCEPT THIS OCCUPATION\s*\?"
    nat_orb_prompt = r"DO YOU REALLY WANT TO WRITE OUT NATURAL ORBITALS\s\?.+\r\n"
    next_menu_headline = r"GENERAL MENU : SELECT YOUR TOPIC"

    process.expect(headline)
    process.expect(end_of_prompt)

    process.sendline("eht")

    cont = True
    while cont:
        idx = process.expect(
            [
                default_prompt,
                charge_prompt,
                occupation_prompt,
                nat_orb_prompt,
                next_menu_headline,
            ]
        )
        if idx == 0:
            # Always accept defaults
            process.sendline("y")
        elif idx == 1:
            process.sendline("{}".format(params["molecule"].get("charge", 0)))
        elif idx == 2:
            # Always accept the produced occupation
            process.sendline("y")
        elif idx == 3:
            process.sendline(
                "{}".format("y" if params.get("write_natural_orbitals", False) else "n")
            )
        elif idx == 4:
            # We ended up in the next menu -> press enter to make the menu "re-render"
            # such that the following code can detect it properly
            process.sendline("")
            cont = False

    # Note: Using eht automatically terminates the occ menu


def set_generic_calc_param(process: pexpect.spawn, instruction: str, value=None):
    if not instruction.strip().endswith("*"):
        print(
            "Warning: Some submenus in define have to be exited via '*' "
            + "- in case of errors, try '*'s in your generic command"
        )
    parts = instruction.split(">")
    parts = [x.strip() for x in parts]
    for currentPart in parts:
        process.sendline(currentPart.format(value))

    # Ensure we arrive back in the main menu
    for _ in range(max(0, len(parts) - 1)):
        # We're relying on being able to get a menu back up by pressing enter
        process.sendline("")


named_calc_params = {
    "max_scf_iterations": ["scf > iter > {}"],
}


def configure_dft_parameter(process: pexpect.spawn, params: Dict[str, Any]):
    summary = r"STATUS OF DFT[_ ]OPTIONS:\s*DFT is\s*(NOT)?\s*used\s*functional\s*([\w-]+)\s*gridsize\s*([\w-]+)"
    functional_not_supported = r"SPECIFIED FUNCTIONAL not SUPPORTED. RESET TO DEFAULT."
    grid_not_supported = r"SPE[ZC]IFIED GRIDSIZE not SUPPORTED. RESET TO DEFAULT"
    disp_corr = r"STATUS OF DFT DISPERSION CORRECTION\s*([\w-]+)?\s*correction is\s*(not)?\s*used"

    # Enter DFT menu
    process.sendline("dft")
    process.expect(summary)

    # Enable DFT
    process.sendline("on")
    process.expect(summary)
    if optional_match_group(process, 1) is not None:
        raise RuntimeError("Enabling DFT failed")

    for key in params:
        if key == "functional":
            process.sendline("func {}".format(params[key]))
            idx = process.expect([functional_not_supported, summary])

            if idx == 0:
                raise RuntimeError(
                    "DFT functional with name '{}' is not supported by your version of TurboMole".format(
                        params[key]
                    )
                )

            assert idx == 1
            active_functional = match_group(process, 2)
            if active_functional.lower() != params[key].lower():
                raise RuntimeError(
                    "Tried to use DFT functional '{}', but define selected '{}' instead".format(
                        params[key], active_functional
                    )
                )
        elif key == "grid":
            # Ensure param type is str
            params[key] = str(params[key])
            process.sendline("grid {}".format(params[key]))
            idx = process.expect([grid_not_supported, summary])

            if idx == 0:
                raise RuntimeError(
                    "DFT grid '{}' is not supported by your version of TurboMole".format(
                        params[key]
                    )
                )

            assert idx == 1
            active_grid = match_group(process, 3)
            if active_grid.lower() != params[key].lower():
                raise RuntimeError(
                    "Tried to use DFT grid '{}', but define selected '{}' instead".format(
                        params[key], active_grid
                    )
                )
        elif key == "dispersion_correction":
            # Leave dft menu
            process.sendline("")
            # Enter dsp menu
            process.sendline("dsp")
            process.expect(disp_corr)
            process.sendline(params[key])
            process.expect(disp_corr)

            active = optional_match_group(process, 2) is None
            if not active:
                raise RuntimeError("Failed at activating dispersion correction")

            method = optional_match_group(process, 1)
            if method is None:
                raise RuntimeError("Unable to extract dispersion correction method")
            method = method
            print("Enabled '{}' dispersion correction".format(method))

            # Leave submenu and re-enter dft menu
            process.sendline("")
            process.sendline("dft")
            process.expect(summary)
        else:
            raise RuntimeError(
                "Undefined keyword in dft option block - should have been caught during verification"
            )

    # The last thing that has been matched has been the summary (across all code paths)
    dft_active = optional_match_group(process, 1) is None
    functional = match_group(process, 2)
    grid = match_group(process, 3)

    if not dft_active:
        raise RuntimeError("DFT activation has failed")

    print("Enabled DFT (functional: '{}'; grid: '{}')".format(functional, grid))

    # Leave DFT menu by sending enter
    process.sendline("")


def configure_ri_parameters(process: pexpect.spawn, params: Dict[str, Any]):
    ri_headline = r"STATUS OF RI-OPTIONS:\s*RI IS\s*(NOT)?\s*USED"
    marij_option = r"threshold for multipole neglect"

    ri_type: str = params.get("type", "ri").lower().replace(" ", "")

    # Handle ri_type synonyms
    if ri_type in ["j", "coulomb", "rij"]:
        ri_type = "ri"
    elif ri_type in ["jk", "coulomb+exchange", "coulomb&exchange"]:
        ri_type = "rijk"

    if not ri_type in ["ri", "rijk"]:
        raise RuntimeError("Unknown RI type '{}'".format(ri_type))

    use_marij = params.get("multipole_acceleration", True)

    # Enable the desired RI method by entering the menu given by ri_type and then sending "on"
    process.sendline(ri_type)
    process.expect(ri_headline)
    process.sendline("on")
    process.expect(ri_headline)

    ri_active = optional_match_group(process, 1) is None

    if not ri_active:
        raise RuntimeError("Failed to enable RI (type: '{}')".format(ri_type))

    # Exit RI menu
    process.sendline("")

    if use_marij:
        # Enable multipole acceleration
        process.sendline("marij")
        process.expect(marij_option)

        # Accept default parameter by sending enter
        process.sendline("")


def configure_x2c_parameter(process: pexpect.spawn, params: Dict[str, Any]):
    if not params.get("enable", False):
        return

    scf_submenu = r"ENTER SCF-OPTION TO BE MODIFIED"
    x2c_question = r"Do you want to switch X2C on\?"
    rlocal_question = r"Do you want to switch rlocal on\?"
    pcc_question = r"Do you want to switch pcc on\?"

    # Enable X2C
    process.sendline("scf")
    process.expect(scf_submenu)
    process.sendline("x2c")
    process.expect(x2c_question)
    process.sendline("y")
    process.expect(scf_submenu)

    if params.get("local_approx", True):
        process.sendline("rlocal")
        process.expect(rlocal_question)
        process.sendline("y")
        process.expect(scf_submenu)

    if params.get("picture_change_corr", True):
        process.sendline("pcc")
        process.expect(pcc_question)
        process.sendline("y")
        process.expect(scf_submenu)

    # Exit SCF menu
    process.sendline("")


def configure_calc_params(process: pexpect.spawn, params: Dict[str, Any]):
    headline = r"GENERAL MENU : SELECT YOUR TOPIC"
    end_of_prompt = r"\* or q\s*: END OF DEFINE SESSION"
    scf_submenu = r"ENTER SCF-OPTION TO BE MODIFIED"

    process.expect(headline)
    process.expect(end_of_prompt)

    if not "calculation" in params:
        print("Using default calculation parameter")
        process.sendline("*")
        return

    calc_params = params["calculation"]
    if len(calc_params) == 0:
        raise RuntimeError("calculation object must not be empty")

    for current in calc_params:
        if current == "generic":
            # Those are handled last and separately
            continue
        if current == "dft":
            configure_dft_parameter(process, params=calc_params[current])
        elif current == "ri":
            configure_ri_parameters(process, params=calc_params[current])
        elif current in named_calc_params:
            value = calc_params[current]

            if type(value) == bool:
                value = "y" if value else "n"

            for instruction in named_calc_params[current]:
                set_generic_calc_param(process, instruction, value)

                process.expect(headline)
                process.expect(end_of_prompt)
        elif current == "finite_nucleus":
            process.sendline("scf")
            process.expect(scf_submenu)
            process.sendline("finnuc")
            process.expect(r"Do you want to switch finnuc on\?")
            if calc_params[current]:
                process.sendline("y")
                process.expect("Finite nucleus model selected")
            else:
                process.sendline("n")
            # Leave SCF menu again
            process.sendline("")
            process.expect(headline)
        elif current == "x2c":
            configure_x2c_parameter(process, params=calc_params[current])
        else:
            raise RuntimeError(
                "Unknown calculation option - should have been caught during parameter validation"
            )

    # Generic option instructions to cover all cases for which we don't have pre-defined options
    # The syntax is a simple
    # first > second > third > value
    # where the different parts (separated by ">") will be entered one after another
    if "generic" in calc_params:
        for instruction in calc_params["generic"]:
            set_generic_calc_param(process, instruction)

            process.expect(headline)
            process.expect(end_of_prompt)

    process.sendline("*")


def run_define(params: Dict[str, Any], debug: bool = False, timeout: int = 10):
    if os.path.exists("control") or os.path.exists("tmp.input"):
        raise RuntimeError(
            "prep_turbomole_calc can't be used in a directory where remnants of a prior define run are located "
            + "- delete all old files or use a different directory"
        )

    process = pexpect.spawn("define")
    process.timeout = timeout
    if debug:
        process.logfile = sys.stdout.buffer

    setup(process, params)
    configure_geometry(process, params)
    configure_basis_set(process, params)
    configure_occupation(process, params)
    configure_calc_params(process, params)


def handle_geometry_conversion(geom_path: str, base_path: str) -> str:
    if not os.path.isabs(geom_path):
        geom_path = os.path.join(base_path, geom_path)

    _, file_ext = os.path.splitext(geom_path)

    if file_ext.lower() == ".xyz":
        # Convert XYZ to TurboMole format
        coord_file = open("coord", "w")
        subprocess.run(["x2t", geom_path], stdout=coord_file).check_returncode()

        return "coord"
    elif not len(file_ext) == 0:
        raise RuntimeError(
            "Can only convert XYZ geometries to TurboMole format, but got '%s'"
            % file_ext
        )

    return geom_path


def handle_legacy_parameter(params: Dict[str, Any]) -> Dict[str, Any]:
    if "calculation" in params:
        calc_params = params["calculation"]

        if "dispersion_correction" in calc_params:
            if "dft" not in calc_params:
                print(
                    "Warning: Ignoring legacy dispersion_correction parameter as no DFT calculation will be performed"
                )
                del calc_params["dispersion_correction"]
            else:
                dft_options = calc_params["dft"]

                if "dispersion_correction" in dft_options:
                    raise RuntimeError(
                        "Legacy dispersion_correction parameter conflicts with explicit specification in dft group"
                    )

                dft_options["dispersion_correction"] = calc_params[
                    "dispersion_correction"
                ]
                del calc_params["dispersion_correction"]
                calc_params["dft"] = dft_options

        if len(calc_params) == 0:
            del params["calculation"]

    if "geometry" in params:
        if not "molecule" in params:
            params["molecule"] = {"geometry": params["geometry"]}
            del params["geometry"]
        else:
            raise RuntimeError(
                "Can't use legacy 'geometry' and 'molecule' option simultaneously"
            )

    molecule_options = params.get("molecule", None)
    if molecule_options is not None:
        if "detect_symmetry" in params:
            if "detect_symmetry" in molecule_options:
                raise RuntimeError("Conflicting sets of options for 'detect_symmetry'")

            molecule_options["detect_symmetry"] = params["detect_symmetry"]
            del params["detect_symmetry"]

        if "use_internal_coords" in params:
            if "use_internal_coords" in molecule_options:
                raise RuntimeError(
                    "Conflicting sets of options for 'use_internal_coords'"
                )

            molecule_options["use_internal_coords"] = params["use_internal_coords"]
            del params["use_internal_coords"]
        if "charge" in params:
            if "charge" in molecule_options:
                raise RuntimeError("Conflicting set of options for 'charge'")
            molecule_options["charge"] = params["charge"]
            del params["charge"]

    if "use_ecp" in params:
        basis_set_options = params.get("basis_set", None)
        if basis_set_options is None:
            raise RuntimeError(
                "Can't specify use_ecp option without specifying a basis set"
            )

        basis_set_options["use_ecp"] = params["use_ecp"]
        del params["use_ecp"]

    return params


def expand_param_shortcuts(params: Dict[str, Any]) -> Dict[str, Any]:
    if "molecule" in params:
        if type(params["molecule"]) is str:
            params["molecule"] = {"geometry": params["molecule"]}

        molecule_options = params["molecule"]
        assert type(molecule_options) is dict
        if "isotopes" in molecule_options:
            assert type(molecule_options["isotopes"]) is dict

            for key in molecule_options["isotopes"]:  # type: ignore
                if type(molecule_options["isotopes"][key]) is int:
                    molecule_options["isotopes"][key] = {
                        "nucleon_count": molecule_options["isotopes"][key]
                    }

    if "basis_set" in params and type(params["basis_set"]) is str:
        params["basis_set"] = {"all": params["basis_set"]}

    if "calculation" in params:
        calc_options = params["calculation"]

        if "dft" in calc_options and type(calc_options["dft"]) is str:
            calc_options["dft"] = {"functional": calc_options["dft"]}
        if "ri" in calc_options and type(calc_options["ri"]) is str:
            calc_options["ri"] = {"type": calc_options["ri"]}
        if "x2c" in calc_options and type(calc_options["x2c"]) is bool:
            calc_options["x2c"] = {"enable": calc_options["x2c"]}

    return params


def main():
    parser = argparse.ArgumentParser(
        description="Run define with a set of pre-defined parameters in order to prepare a TurboMole computation"
    )
    parser.add_argument(
        "parameter",
        help="Path to the parameter file",
        metavar="PATH",
        default="calculation_parameter.json",
        nargs="?",
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
        "--cd",
        help="Execute in the directory of the parameter file instead of the present working directory",
        default=False,
        action="store_true",
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

    param_dir: str = os.path.dirname(args.parameter)
    if len(param_dir) == 0:
        param_dir = "."
    if args.cd:
        os.chdir(param_dir)

    parameter = expand_param_shortcuts(params=parameter)
    parameter = handle_legacy_parameter(params=parameter)

    if not "molecule" in parameter or not "geometry" in parameter["molecule"]:
        raise RuntimeError("'molecule > geometry' option is mandatory!")

    parameter["molecule"]["geometry"] = handle_geometry_conversion(
        parameter["molecule"]["geometry"], param_dir
    )

    validate_parameter(params=parameter)

    run_define(parameter, debug=args.debug, timeout=args.timeout)


if __name__ == "__main__":
    main()
