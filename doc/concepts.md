# Concepts


## Databag

The databag is a key-value store (`dict`) that is loaded with values from 
`databag.yaml` initially and then accumulates other values as the stack is 
processed. It is serialised to `output_databag.yaml` when a run completes.

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