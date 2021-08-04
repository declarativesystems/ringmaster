# Ringmaster Handlers

Each file in your stack directory is processed by a different handler. Handlers
are just Python functions that are executed when a filename matches the handler
pattern.

Ringmaster supports these handlers:

## *.sh

* Normal bash scripts
* Each variable in databag exposed as environment variables
* Put values in databag by writing JSON to `$intermediate_databag_file`
* script will be run with `$1 == $up_verb` if stack is creating or 
  `$1 == $down_verb` if stack is being destroyed  

## *.cloudformation.yaml

* Normal cloudformation in yaml format
* Parameters are converted to snake_case and looked up from databag
* Outputs are converted to snake_case and added to databag

## *.remote_cloudformation.yaml

* Remotely hosted cloudformation scripts to get around 51200 byte upload
  hard limit
* Handled the same as local cloudformation scripts
* A copy of the remote file will be downloaded for your own records and
  for parameter pre-processing

## *.kubectl.yaml

* Databag variables are available and can be inserted as ${variable_name}
* Ringmaster pre-process the file to substitute variables and saves the
  output as `*.kubectl.processed.yaml`
* `*.kubectl.processed.yaml` files are just normal kubectl files

## kustomization.yaml

* Processed with `kubectl (apply|delete) -k`
* Not changed by ringmaster in any way
* Be sure to also download any required files

## *.ringmaster.py

* Rudimentary plugin system
* Normal python scripts
* Top level variable `databag` will be set with the current databag
* To make new data available to other stages, just add it to `databag`
* Ringmaster runs your script like this:
    1. set `databag`
    2. call `main()` with argument `verb` which indicates whether we are 
       creating or destroying

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