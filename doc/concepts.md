# Concepts

## Stacks

Ringmaster refers to a directory of scripts to run through as a _stack_:

```
my_stack/
├── 0010-step1
└── 0020-step2
```

* The stack name is the name of the directory, so in this case the stack is
  called `my_stack`
* Stacks are just directories
* Have ringmaster process your stack like this:
    * `ringmaster my_stack up`
    * `ringmaster my_stack down`

## Execution order

Directories are processed in alphabetical order so by prefixing directories
with a number we can easily control the order:

```
├── 0010-this-is-first
├── 0020-this-is-second
├── 0030-this-is-third
```

The _gaps_ in the sequence allow extra steps to be inserted without 
renumbering - although you may still want to renumber to satisfy OCD: 

```
├── 0010-this-is-first
├── 0011-uh-oh
├── 0020-this-is-second
├── 0030-this-is-third
```

To further reduce the need for renumbering similar steps can be grouped into
number ranges, eg:

* `00xx` - General AWS setup that can be done before EKS is setup (IAM, EFS, 
   etc)
* `01xx` - EKS cluster setup
* `02xx` - EKS cluster services 

_Numbering is completely optional but is a simple way to control ordering_ 


## Databag

The databag is a key-value store (`dict`) that is loaded with values from 
`databag.yaml` initially and then accumulates other values as the stack is 
processed. It is serialised to `output_databag.yaml` when a run completes and
if `output_databag.yaml` is present, this will be used instead of 
`databag.yaml` for subsequent runs.

The contents of the databag are made available as each step is processed. This
lets us do things like lookup EKS details such as public/private subnet IDs and
use the values directly in later steps.

To share a databag as the input to another stack, just copy the file, eg:

```shell
ringmaster up
cp output_databag.yaml ../customer_stack/databag.aml
```

This way you could have one stack to build your EKS cluster and other stacks to
deploy infrastructure as new projects or customers are onboarded.

**Example**

Lets say you have some cloudformation to setup an RDS server:

```yaml
Parameters:
  VpcPrivateSubnet1Aid:
    Type: String
  VpcPrivateSubnet2Aid:
    Type: String
Resources:
  DBSubnetGroup:
    Type: "AWS::RDS::DBSubnetGroup"
    Properties:
      DBSubnetGroupDescription: !Sub "${AWS::StackName} DBSubnet"
      SubnetIds:
        - !Ref VpcPrivateSubnet1Aid
        - !Ref VpcPrivateSubnet2Aid
  RDSDBInstance:
    Type: "AWS::RDS::DBInstance"
    # ...
Outputs:
  RDSDBInstanceAddress:
    Value: !GetAtt RDSDBInstance.Endpoint.Address
    Export:
      Name: !Sub "db-rds-address"
```

There are 2x input parameters:
* `VpcPrivateSubnet1Aid`
* `VpcPrivateSubnet2Aid`

Ringmaster will translate these to snake_case which is the naming convention 
for databag fields and will attempt to lookup:

* `vpc_private_subnet1_aid`
* `vpc_private_subnet2_aid`

Everything in the `Output` section will also be added to the databag for the
next script to use by reversing this logic, so this stack add the value
`db_rds_address` to the databag which would be set to the address of the RDS
instance.

If you now need to feed this value back to your kubernetes deployment, you
could do something like this:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: someapp
spec:
  template:
    spec:
      containers:
        - name: someapp
          env:
            - name: DB_ADDRESS
              value: ${db_rds_address}
```

