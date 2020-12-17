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

`${name_of_variable}` identifies a substitution variable. The entire expression
will be replaced with the value of `name_of variable` during processing

## String literals

String literals can be inserted into interpolation expressions by using single
quotes `'foo'`

## Filters

Filter expressions collect the output of the expression and transform it. They
are identified by the pipe `|` character.

* Only `|base64` is supported at the moment

## Functions

Functions allow data to be resolved from outside the databag

* Only the `env()` function is supported at the moment

## Missing variables

Missing variables will trigger an error advising the name of the missing 
variable.

## Loops, conditionals, etc

* Not supported

## Example

_See the complete file at 
[docker.default.secret_kubectl.yaml](../examples/0130-docker-secret/docker.default.secret_kubectl.yaml)

```yaml
  .dockerconfigjson: >
    {
      "auths": {
        "https://${docker_server}": {
          "auth": "${docker_email':'env(docker_password)|base64}",
          "email": "${docker_email}"
        }
      }
    }
```

* `docker_server` and `docker_email` are simple values resolved from the databag
* `auth` makes uses of all the current interpolation features:
    1. `docker_email` is resolved from databag
    2. string literal `:` is appended to it
    3. `docker_password` is resolved from the environment
    4. All of this data is base64 encoded