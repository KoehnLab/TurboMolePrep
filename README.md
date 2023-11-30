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
    "geometry": "coord",
    "use_redundant_coords": true,
    "detect_symmetry": true,
    "basis_set": {
        "all": "def2-TZVPP"
    },
    "charge": 0,
    "write_natural_orbitals": false
}
```

