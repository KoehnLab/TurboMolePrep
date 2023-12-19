# TurboMolePrep

[TurboMole](https://www.turbomole.org/) ships with the `define` utility that can be used to set up calculations interactively. While this can be nice
in certain cases, it can quickly become somewhat cumbersome if routine calculations have to be set up. Or if one wishes to use (almost) the same
parameters in various different calculations. In the latter case, besides being time-consuming, one can make errors leading to more parameters being
different in the calculations than originally anticipated.

In such cases, it would be really handy, if TurboMole had a simple input file in which users could input their parameters which will always lead to
the same calculation setup. Often people end up helping themselves by automating the input for the `define` program by using something like
```bash
define <<<EOF

a coord
*
b all def2-TZVPP
*
…
EOF
```
which then blindly feeds the respective characters into `define`, completely oblivious to what `define` is currently doing or asking for. Therefore,
this approach is very brittle and on top, these kind of scripts are very hard to parse for a fellow human being.

This script enables automated use of `define` in a way that is context-sensitive (i.e. it knows what `define` is currently up to - this is made
possible thanks to [pexpect](https://github.com/pexpect/pexpect)) and in a way that makes the used parameters very easy to extract for humans as well.
In order to do that, the parameter specification is done in a [JSON](https://www.json.org/json-en.html) file. This file is passed to the script, which
will pass the information down to `define` in the necessary format. A sample setup could look like this:
```json
{
    "title": "My awesome TurboMole calculation",
    "molecule": {
        "geometry": "my_geom.xyz",
        "use_internal_coords": true,
        "charge": 0,
        "detect_symmetry": true
    },
    "basis_set": "def2-TZVPP"
    "write_natural_orbitals": false
}
```

## Setup

In order to use this script, install its dependencies via
```bash
pip3 install -r requirements.txt
```
or, if you don't have `pip3` installed as a standalone module, via
```bash
python3 -m pip install -r requirements.txt
```

Once all dependencies are installed, you can use this script to your heart's desire.


## Configuration files

The configuration is done by means of a JSON file. It provides various options that can be specified. All options are optional except for the
`geometry` one.


### Top-level options

These options are provided as simple key-value pairs on the first level in the JSON hierarchy.

| **Name** | **Description** | **Type** | **Default** |
| -------- | --------------- | -------- | ----------- |
| `basis_set` | Specify the basis set(s) to use | `String` or sub-object (see below) | TurboMole's default |
| `molecule` | Specifies the path to the file that contains the geometry of the system to be calculated. Automatic conversion from XYZ files to TurboMole format is supported. Relative paths are relative to the JSON file's directory. | `String` or nested sub-object (see below) | - |
| `title`  | Sets the title of the calculation | `String` | No title |
| `write_natural_orbitals` | Whether to write out natural orbitals (after extended Hückel guess) | `Boolean` | `false` |


### molecule options

In case the argument to the `molecule` is of type string, the value is taken to specify the molecule's geometry (which is mandatory!)

| **Name** | **Description** | **Type** | **Default** |
| -------- | --------------- | -------- | ----------- |
| `charge` | The charge of the system | `Integer` | `0` |
| `detect_symmetry` |  Whether to let TurboMole autodetect the system's symmetry | `Boolean` | `true` |
| `geometry` | The path to the geometry specification of the system/molecule | `String` | - |
| `use_internal_coords` | Whether to generate and use internal, redundant coordinates for the molecule (very useful for geometry optimizations) | `Boolean` | `true` |
| `isotopes` | Specification of specific isotopes to use | sub-object (see below) | TurboMole's default |


#### isotope options

The value of the `isotopes` sub-option is a nested JSON object whose keys are expected to be element symbols and whose values can either be an integer
or another nested sub-object with keys `nucleon_count` and `gyromagnetic_ratio`. This allows to specify the gyromagnetic ratio for nuclei that
TurboMole doesn't support out-of-the-box.

Example:
```json
"isotopes": {
    "C": 13,
    "H": {
        "nucleon_count": 3,
        "gyromagnetic_ratio": 5.95799369
    }
}
```


### basis\_set options

The argument to the `basis_set` option can be a nested JSON object. In this case, one can specify basis sets on a per-element-basis.

Basis sets are assigned as key-value pairs where the key is the group to which to apply the chosen basis set (indicated by the value). The group be
anything that `define` also accepts, e.g.

- `all` to assign the same basis set to all atoms
- element label to assign the basis set to all atoms of the given element. Note: contrary to the `define` input, no extra quotation marks are
  necessary
- Indices to assign the corresponding elements the chosen basis sets. Indices start at `1` (hydrogen) and index ranges and
  enumerations (e.g. `1,2,6-9`) are permitted

Note that groups are always processed from least-specific to most-specific. That means that it is possible to use the `all` group to set a default
basis set that is subsequently overwritten for certain elements.

Example:
```json
"basis_set": {
    "all": "def2-SVP",
    "Cu": "def2-TZVPP",
    "3,4": "dz"
}
```

Additionally, the following options can be specified:

| **Name** | **Description** | **Type** | **Default** |
| -------- | --------------- | -------- | ----------- |
| `use_ecp` | Whether any ECPs shall be used. If not, the script tries to remove all assigned ECPs (but sometimes TurboMole can be stubborn about this) | `Boolean` | `true` |

## calculation

This option group defines parameters for the calculation that shall be performed.

| **Name** | **Description** | **Type** |
| -------- | --------------- | -------- |
| `dft` | Turns on DFT with the given parameters. If the value is a string, then that will be used as the name of the functional | `String` or sub-object (see below) |
| `max_scf_iterations` | Sets the maximum SCF iterations | `Integer` |
| `ri` | Enables use of the resolution-of-the-identity (density-fitting) approximation for the chosen integrals | `String` or sub-object (see below) |
| `x2c` | Enables or disables X2C | `Boolean` |

Example:
```json
"calculation": {
    "dft": "pbe0"
}
```

#### dft options

The argument of the `dft` option can be a nested JSON object, which can have the following fields
| **Name** | **Description** | **Type** | **Default** |
| -------- | --------------- | -------- | ----------- |
| `functional` | Specifies the functional to use | `String` | TurboMole's default |
| `grid` | Specifies the integration grid that shall be used | `String` or `Integer` | TurboMole's default |
| `dispersion_correction` | What disperson correction method to use | `String` | `off` |


#### ri options

If the value of the `ri` option is of type `String`, it is a shorthand for the following, more explicit notation:
```json
"ri": {
    "type": <value>
}
```
where `<value>` is the string given to the `ri` option.

If `ri` is directly given a nested JSON object, then this object can have the following options set:
| **Name** | **Description** | **Type** | **Default** |
| -------- | --------------- | -------- | ----------- |
| `type` | Which integrals to decompose | `String` (see below) | `Coulomb` |
| `multipole_acceleration` | Whether to enable use of mulitpole acceleration (`marij`) for the Coulomb contributions | `Boolean` | `true` |

`type` decides whether to only apply RI for Coulomb-like contributions or whether to also apply them to exchange-like contributions. The allowed
keywords and their effect are (case-insensitive and space-insensitive)
- `ri`: Coulomb-only
- `rij`: Coulomb-only
- `coulomb`: Coulomb-only
- `J`: Coulomb-only
- `rijk`: Coulomb \& Exchange
- `JK`: Coulomb \& Exchange
- `Coulomb & Exchange`: Coulomb \& Exchange
- `Coulomb + Exchange`: Coulomb \& Exchange


### generic

This sub-group contains generic specification on what to enter in `define`'s final configuration menu (where the parameters for the calculation itself
are specified). It is meant as a fall-back for all options that don't have a dedicated, named calculation option.

Note that the `generic` group is a JSON **array** and not a nested object. All entries in the array are processed in-order and are of the form
```
a > b
```
which translates directly to
1. Enter the submenu with name `a`
2. Enter the value `b`
3. Return back to the root calculation parameter menu

Submenus can be nested arbitrarily deep. E.g.
```
scf > conv > 8
```
sets the convergence threshold for SCF calculations to $10^{-8}$.

Example:
```json
"generic": [
    "scf > conv > 8",
    "dsp > d4"
]
```

