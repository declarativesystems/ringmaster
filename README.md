# ringmaster
```
         _
       _[_]_
       _(_)______.-'`-.
      /, >< ,----'     `-._.-'*
      \\|::|  Welcome to the Circus
        |/\|  We already got enough Clowns,
        ||||  You got any experiance with
        ||||  Being shot from a canon??
     __(_/\_)
    /`-..__.,-'\
   /   __/\__   \
   `._ \    / _.'MJP
      ``|/\|-'
```
## Quickstart

### 1. Setup

```shell
# ringmaster init --aws
```

Grab a bunch of cloudformation scripts off amazon 

### 2. Create (VPC) and cluster

```shell
ringmaster stack up
```


## Reference

### Concepts

#### Databag

The databag is a key-value store (`dict`) that is loaded with values from 
`databag.yaml` initially and then accumulates other values of interest as the
stack is built. It is serialised to `output_databag.yaml` as a run completes.

The contents of the databag are made available as each step is processed. This
lets us do things like lookup EKS details such as public/private subnet IDs and
use the values directly in later steps.

#### AWS Authentication
This is handled directly by the 
[Boto3 API](https://aws.amazon.com/sdk-for-python/) which uses the files in 
`~/.aws` to configure credentials.

The default _profile_ will be used automatically, use the `AWS_PROFILE` 
environment variable to use a different one:

```
AWS_PROFILE="someprofile" ringmaster ...
```

All work is done inside a single region which is controlled by databag value:
```
aws_region: "us-east-1" # eg
```

 


### Directory structure

```
.
├── databag.yaml
├── output_databag.yaml
└── stack
    ├── down
    │     ├── 0010
    │     │     └── cluster.sh
    │     └── 0020
    │         └── infra.cloudformation.yaml -> ../../shared/infra.cloudformation.yaml
    ├── shared
    │     └── infra.cloudformation.yaml
    └── up
        ├── 0010
        │     └── infra.cloudformation.yaml -> ../../shared/infra.cloudformation.yaml
        ├── 0020
        │     └── cluster.sh
        ├── 0030
        │     └── get_eks_cluster_info
        ├── 0040
        │     ├── iam_policy.json
        │     └── load_balancer_iam.sh
        ├── 0050
        │     └── iam_service_account.sh
        ├── 0060
        │     ├── crds.yaml
        │     ├── deploy_load_balancer.sh
        │     └── kustomization.yaml
        ├── 0070
        │     ├── csidriver.kubectl.yaml
        │     └── storage_security_groups.ringmaster.py
        ├── 0080
        │     ├── claim.kubectl.yaml
        │     ├── pv.kubectl.yaml
        │     └── storageclass.kubectl.yaml
        └── 0090
            └── solarwinds_papertrail.yaml

```


### filetypes

#### *.sh
* normal bash scripts
* each variable in databag exposed as environment variables
* put values in databag by writing JSON to `$intermediate_databag_file`

#### *.cloudformation.yaml
* normal cloudformation in yaml format
* parameters are converted to snake_case and looked up from databag
* outputs are converted to snake_case and added to databag

#### *.remote_cloudformation.yaml
* Remotely hosted cloudformation scripts to get around 51200 byte upload
  hard limit
* Handled the same as local cloudformation scripts
* A copy of the remote file will be downloaded for your own records and
  for parameter pre-processing

#### *.kubectl.yaml
* databag variables are available and can be inserted as ${variable_name}
* ringmaster pre-process the file to substitute variables and saves the
  output as `*.kubectl.processed.yaml`
* `*.kubectl.processed.yaml` files are just normal kubectl files

#### solarwinds_papertrail.yaml
* single purpose file to configure solarwinds papertrail at cluster level
* ringmaster will perform the entire installation
* `kustomization` files will be saved to in a directory `download` within the 
  current step 

#### kustomization.yaml
* processed with `kubectl (apply|delete) -k`
* not changed by ringmaster in any way
* be sure to also download any required files

#### *.ringpaster.py
* Rudimentary plugin system
* Normal python scripts
* Top level variable `databag` will be set with the current databag
* To make new data available to other stages, just add it to `databag`
* Execution:
    1. set `databag`
    2. call `main()` 

#### get_eks_cluster_info
* Empty file
* Tells ringmaster to lookup eks cluster info and add it to databag:
    * `cluster_vpc_cidr`
    * `cluster_private_subnets`
    * `cluster_private_subnet_{n}`
    * `cluster_public_subnets`
    * `cluster_public_subnet_{n}`

# *.snowflake.sql
* Bunch of SQL commands to run against snowflake
* Configure snowflake credentials at `~/.ringmaster/snowflake.yaml`
* Placeholders will be substituted and the result saved to 
  `file.snowflake.processed.sql`
* Each line **must** end with `;`
* Lines starting `--` will be discarded
* One statement per line, but long statements can be split over multiple lines