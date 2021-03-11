# Variables

Ringmaster is not a scripting language and only offers the bare minimum to
pass values between scripts.

Not all handlers support variable substitution, eg:

* Cloudformation - use parameters instead
* remote_cloudformation.yaml - use parameters instead
* Bash - use environment variables
* Python - use `data` field

Variable substitution is most useful for things like Kubernetes deployment
descriptors/secrets.

## Assigning

Variables are assigned on creation:

* In the databag - `databag.yaml` 
* As the output of script

_It is not possible to assign variables at the time of evaluation_

## Resolution

The databag is a simple `dict` (AKA map, associative array, hash...). The
latest assignment replaces any existing one.

At the end of a ringmaster run, all resolved values are saved to 
`output_databag.yaml`. 

**`output_databag.yaml` will be loaded instead of `databag.yaml` if it exists**

## Scope

Databag variables are flat within each stack directory. By creating multiple 
stacks you can support multiple independent scopes and by copying 
`output_databag.yaml` between scopes, you can pass vetoed variables 

## Naming

* lower-case snake case, eg: `my_variable`
* variable names are case-sensitive

## Interpolation expressions

Interpolation is processed by [Jinja2](https://jinja.palletsprojects.com/)
so behaves as documented. `{{ name_of_variable }}` identifies a substitution
variable. The entire expression will be replaced with the value of 
`name_of_variable` during processing

## Missing variables

Missing variables will trigger an error advising the name of the missing 
variable.

