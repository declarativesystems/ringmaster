# Workflow

_Zero to hero_

## 1. Stack assembly

_Lets go super deluxe and get everything_

```shell
ringmaster get stack/0010-iam https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0010-iam
ringmaster get stack/0020-efs https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0020-efs
ringmaster get stack/0030-vpc https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0030-vpc
ringmaster get stack/0110-eks-cluster https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0110-eks-cluster
ringmaster get stack/0120-eks-cluster-access https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0120-eks-cluster-access
ringmaster get stack/0120-vpc-peering https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0120-vpc-peering
ringmaster get stack/0130-docker-secret https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0130-docker-secret
ringmaster get stack/0140-k8s-efs-driver https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0140-k8s-efs-driver
ringmaster get stack/0150-efs-mount-targets https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0150-efs-mount-targets
ringmaster get stack/0160-efs-pv https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0160-efs-pv
ringmaster get stack/0210-solarwinds-papertrail https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0210-solarwinds-papertrail
ringmaster get stack/0220-external-secrets https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0220-external-secrets
ringmaster get stack/0230-external-dns https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0230-external-dns
ringmaster get stack/0320-k53certbot https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0320-k53certbot
ringmaster get stack/0330-aws-load-balancer https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0330-aws-load-balancer
ringmaster get stack/0340-ambassador https://raw.githubusercontent.com/declarativesystems/ringmaster/release0/examples/0340-ambassador
```

_This will create the following directory structure_

```shell
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
├── 0110-eks-cluster
│     ├── cluster.eksctl.yaml
│     └── metadata.yaml
├── 0120-eks-cluster-access
│     ├── iam_access.sh
│     └── metadata.yaml
├── 0120-vpc-peering
│     ├── metadata.yaml
│     └── vpcpeering.cloudformation.yaml
├── 0130-docker-secret
│     ├── docker.default.secret_kubectl.yaml
│     ├── docker.kube-system.secret_kubectl.yaml
│     └── metadata.yaml
├── 0140-k8s-efs-driver
│     ├── csidriver.kubectl.yaml
│     ├── metadata.yaml
│     └── storageclass.kubectl.yaml
├── 0150-efs-mount-targets
│     ├── efs_mount_targets.ringmaster.py
│     └── metadata.yaml
├── 0160-efs-pv
│     ├── claim.kubectl.yaml
│     ├── metadata.yaml
│     └── pv.kubectl.yaml
├── 0210-solarwinds-papertrail
│     ├── metadata.yaml
│     └── solarwinds_papertrail.yaml
├── 0220-external-secrets
│     ├── helm_deploy.yaml
│     └── metadata.yaml
├── 0230-external-dns
│     ├── externaldns.kubectl.yaml
│     └── metadata.yaml
├── 0320-k53certbot
│     ├── 0-zerossl.secret_kubectl.yaml
│     ├── k53certbot.kubectl.yaml
│     └── metadata.yaml
├── 0330-aws-load-balancer
│     ├── helm_deploy.yaml
│     ├── kustomization.yaml
│     └── metadata.yaml
└── 0340-ambassador
    ├── helm_deploy.yaml
    └── metadata.yaml

```


## 2. Create infrastructure

```shell
ringmaster --debug stack up
```
