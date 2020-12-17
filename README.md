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
gits or daemons. 

There is also no custom DSL or new programming language to learn, although
there is a simple templating system.

Ringmaster is just files on a disk and calls to other systems.

## How does it work?

You create a directory of scripts to process, like this:

```
stack/
├── 0010-iam
│     ├── AWSLoadBalancerController.iam_policy.json
│     ├── Certbot.iam_policy.json
│     ├── EksDeploy.iam_policy.json
│     ├── EksExternalSecrets.iam_policy.json
│     ├── ExternalDns.iam_policy.json
│     └── metadata.yaml
├── 0020-efs
│     ├── efs.cloudformation.yaml
│     └── metadata.yaml
├── 0030-vpc
│     ├── metadata.yaml
│     ├── vpc.remote_cloudformation.yaml
│     └── vpc.yaml
...
```

Then you tell ringmaster to process the scripts, like this:

`ringmaster stack up`

Ringmaster will carry out the create action of each script, running each 
script in alphabetical order by directory and then file

`ringmaster stack down`

Ringmaster will carry out the delete action of each script, in reverse
alphabetical order

**The `up` and `down` actions are idempotent so you can run them as many times
as you like**

## Workstation Setup

Install and configure:
* AWS CLI v2 with IAM admin rights on your AWS account
* eksctl
* kubectl
* helm v3
* Python 3 + pip

**You must use EKS compatible versions:** 
https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html 


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
3. [Handlers](doc/handlers.md)
4. [Worked Example](doc/worked_example.md)




 


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


