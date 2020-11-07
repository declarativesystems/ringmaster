# ringmaster

## Quickstart

### 1. Setup

```shell
# not working yet  .... ringmaster init --aws
```

Grab a bunch of cloudformation scripts off amazon 

### 2. Create (VPC) and cluster

```shell
ringmaster up
```


## Reference

### filetypes

#### *.sh
* normal bash scripts
* each variable in databag exposed as environment variables
* put values in databag by writing JSON to `$intermediate_databag_file`

#### *.cloudformation.yaml
* normal cloudformation in yaml format
* parameters are converted to snake_case and looked up from databag
* outputs are converted to snake_case and added to databag

#### *.kubectl.yaml
* databag variables are available and can be inserted as ${variable_name}
* ringmaster pre-process the file to substitute variables and saves the
  output as `*.kubectl.processed.yaml`
* `*.kubectl.processed.yaml` files are just normal kubectl files

#### solarwinds_papertrail.yaml
* single purpose file to configure solarwinds papertrail at cluster level
* ringmaster will perform the entire installation

#### kustomization.yaml
* processed with `kubectl (apply|delete) -k`
* not changed by ringmaster in any way
* be sure to also download any required files