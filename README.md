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

Ringmaster organises a bunch of other tools on your behalf so that you dont
have to. The aim is you can create, updated and delete entire stacks crossing
cloudformation, EKS, kubectl, helm and random Python/BASH scripts with a single
command.

Ringmaster helps you create and share your automation scripts with others so
you can get up and running as quick as possible. There are no agents, hubs, 
gits or daemons. Just files on a disk and calls to other systems.

## Quickstart

### 1. Setup




### 2. Create (VPC) and cluster

```shell
ringmaster stack up
```

## Setup
* AWS CLI
* eksctl
* kubectl
* helm
* Python 3 + pip



## Reference

1. [Concepts](doc/concepts.md)
2. [Authentication](doc/authentication.md)
2. [Handlers](doc/handlers.md)




 


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


