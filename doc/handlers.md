# Ringmaster Handlers

## *.sh

* normal bash scripts
* each variable in databag exposed as environment variables
* put values in databag by writing JSON to `$intermediate_databag_file`

## *.cloudformation.yaml

* normal cloudformation in yaml format
* parameters are converted to snake_case and looked up from databag
* outputs are converted to snake_case and added to databag

## *.remote_cloudformation.yaml

* Remotely hosted cloudformation scripts to get around 51200 byte upload
  hard limit
* Handled the same as local cloudformation scripts
* A copy of the remote file will be downloaded for your own records and
  for parameter pre-processing

## *.kubectl.yaml

* databag variables are available and can be inserted as ${variable_name}
* ringmaster pre-process the file to substitute variables and saves the
  output as `*.kubectl.processed.yaml`
* `*.kubectl.processed.yaml` files are just normal kubectl files

## solarwinds_papertrail.yaml

* single purpose file to configure solarwinds papertrail at cluster level
* ringmaster will perform the entire installation
* `kustomization` files will be saved to in a directory `download` within the 
  current step 

## kustomization.yaml

* processed with `kubectl (apply|delete) -k`
* not changed by ringmaster in any way
* be sure to also download any required files

## *.ringmaster.py

* Rudimentary plugin system
* Normal python scripts
* Top level variable `databag` will be set with the current databag
* To make new data available to other stages, just add it to `databag`
* Ringmaster runs your script like this:
    1. set `databag`
    2. call `main()` 

## *.snowflake.sql

* Bunch of SQL commands to run against snowflake
* Configure snowflake credentials at `~/.ringmaster/snowflake.yaml`
* Placeholders will be substituted and the result saved to 
  `file.snowflake.processed.sql`
* Each line **must** end with `;`
* Lines starting `--` will be discarded
* One statement per line, but long statements can be split over multiple lines

## *.snowflake_query.sql

* ONE sql command to run which must be a `SELECT` statement
* Configure snowflake credentials at `~/.ringmaster/snowflake.yaml`
* Placeholders will be substituted and the result saved to 
  `file.snowflake_query.processed.sql`
* Entire processed file will be executed as-is
* Columns in the results will be added to databag using the column name. Use 
  SQL `AS` to set databag name, eg:
  `SELECT  x AS the_name_for_databag`

## helm_deploy.yaml

* Install helm repo and deploy directly
* Repeatable deployments artifactory integration or similar