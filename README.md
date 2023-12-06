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
    "geometry": "my_geom.xyz",
    "use_internal_coords": true,
    "detect_symmetry": true,
    "basis_set": {
        "all": "def2-TZVPP"
    },
    "charge": 0,
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
| `charge` | The charge of the system | `Integer` | `0` |
| `detect_symmetry` |  Whether to let TurboMole autodetect the system's symmetry | `Boolean` | `true` |
| `geometry` | Specifies the path to the file that contains the geometry of the system to be calculated. Automatic conversion from XYZ files to TurboMole format is supported. Relative paths are relative to the JSON file's directory. | `String` | - |
| `title`  | Sets the title of the calculation | `String` | No title |
| `use_ecp` | Whether any ECPs shall be used. If not, the script tries to remove all assigned ECPs (but sometimes TurboMole can be stubborn about this) | `Boolean` | `true` |
| `use_internal_coords` | Whether to generate and use internal, redundant coordinates for the molecule (very useful for geometry optimizations) | `Boolean` | `true` |
| `write_natural_orbitals` | Whether to write out natural orbitals (after extended Hückel guess) | `Boolean` | `false` |


### basis\_set

This option group contains information about the basis set that shall be used. If it is absent, the script will stick to TurboMole's automatically
assigned basis set.

Basis sets are assigned as key-value pairs where the key is the group to which to apply the chosen basis set (indicated by the value). The group be
anything that `define` also accepts, e.g.

- `all` to assign the same basis set to all atoms
- element label to assign the basis set to all atoms of the given element. Note: contrary to the `define` input, no extra quotation marks are
  necessary
- Indices to assign the corresponding atoms the chosen basis sets. Indices start at `1` (the first atom in the geometry) and index ranges and
  enumerations (e.g. `1,2,6-9`) are permitted

Example:
```json
"basis_set": {
    "C": "def2-SVP",
    "Cu": "def2-TZVPP",
    "3,4": "dz"
}
```

## calculation

This option group defines parameters for the calculation that shall be performed.

| **Name** | **Description** | **Type** |
| -------- | --------------- | -------- |
| `dft_grid` | Set the grid to be used in DFT. Does **not** turn on DFT. | `String` or `Integer` |
| `dispersion_correction` | What disperson correction method to use | `String` |
| `functional` | Specify DFT functional and turn on DFT | `String` |
| `max_scf_iterations` | Sets the maximum SCF iterations | `Integer` |
| `x2c` | Enables or disables X2C | `Boolean` |

Example:
```json
"calculation": {
    "functional": "pbe0"
}
```


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

