# Worked Example

_Zero to hero_

## 1. Stack assembly

_Lets go super deluxe and get everything..._

```shell
ringmaster get stack/0010-iam https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0010-iam
ringmaster get stack/0020-efs https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0020-efs
ringmaster get stack/0030-vpc https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0030-vpc
ringmaster get stack/0110-eks-cluster https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0110-eks-cluster
ringmaster get stack/0120-eks-cluster-access https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0120-eks-cluster-access
ringmaster get stack/0130-vpc-peering https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0130-vpc-peering
ringmaster get stack/0140-docker-secret https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0140-docker-secret
ringmaster get stack/0150-k8s-efs-driver https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0150-k8s-efs-driver
ringmaster get stack/0160-efs-mount-targets https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0160-efs-mount-targets
ringmaster get stack/0170-efs-pv https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0170-efs-pv
ringmaster get stack/0210-solarwinds-papertrail https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0210-solarwinds-papertrail
ringmaster get stack/0220-external-secrets https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0220-external-secrets
ringmaster get stack/0230-external-dns https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0230-external-dns
ringmaster get stack/0240-k53certbot https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0240-k53certbot
ringmaster get stack/0250-aws-load-balancer https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0250-aws-load-balancer
ringmaster get stack/0260-ambassador https://raw.githubusercontent.com/declarativesystems/ringmaster/master/examples/0260-ambassador
```

_This will create the following directory structure..._

```shell
stack
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
│     └── vpc.remote_cloudformation.yaml
├── 0110-eks-cluster
│     ├── cluster.eksctl.yaml
│     └── metadata.yaml
├── 0120-eks-cluster-access
│     ├── iam_access.sh
│     └── metadata.yaml
├── 0130-vpc-peering
│     ├── metadata.yaml
│     └── vpcpeering.cloudformation.yaml
├── 0140-docker-secret
│     ├── docker.default.secret_kubectl.yaml
│     ├── docker.kube-system.secret_kubectl.yaml
│     └── metadata.yaml
├── 0150-k8s-efs-driver
│     ├── csidriver.kubectl.yaml
│     ├── metadata.yaml
│     └── storageclass.kubectl.yaml
├── 0160-efs-mount-targets
│     ├── efs_mount_targets.ringmaster.py
│     └── metadata.yaml
├── 0170-efs-pv
│     ├── claim.kubectl.yaml
│     ├── metadata.yaml
│     └── pv.kubectl.yaml
├── 0210-solarwinds-papertrail
│     ├── logging-secret.kube-system.secret_kubectl.yaml
│     ├── metadata.yaml
│     └── solarwinds_papertrail.yaml
├── 0220-external-secrets
│     ├── helm_deploy.yaml
│     └── metadata.yaml
├── 0230-external-dns
│     ├── externaldns.kubectl.yaml
│     └── metadata.yaml
├── 0240-k53certbot
│     ├── 0-zerossl.secret_kubectl.yaml
│     ├── k53certbot.kubectl.yaml
│     └── metadata.yaml
├── 0250-aws-load-balancer
│     ├── crds.yaml
│     ├── helm_deploy.yaml
│     ├── kustomization.yaml
│     └── metadata.yaml
└── 0260-ambassador
    ├── helm_deploy.yaml
    ├── metadata.yaml
    └── values.yaml
```

## 2. Databag

The scripts will lookup values from `databag.yaml` so create these file and add
the expected values - adjust as needed:

```yaml
cluster_name: mycluster
aws_region: us-east-1
aws_account_id: 111122223333
aws_load_balancer_controller_service_name: aws-load-balancer-controller
eks_external_secrets_service_name: external-secrets-kubernetes-external-secrets
ambassador_service_name: ambassador-service
cert_manager_service_name: cert-manager
external_dns_service_name: external-dns
certbot_service_name: certbot-service

# fixme - how to have a single list? (any ideas dear reader)
# ekcsctl uses individual zones...
availability_zone_a: us-east-1a
availability_zone_b: us-east-1b
# cloudformation needs a string...
availability_zones: us-east-1a,us-east-1b
kubernetes_version: "1.18"

# private docker repository - eg artifactory
docker_server: yourserver.jfrog.io
docker_username: bob
docker_email: your@email.com
certbot_admin_email: your@email.com
eks_cluster_admin_arn: arn:aws:iam::111122223333:user/some.user
```


## 3. export secret values

These scripts are expecting some secret values exported from your environment:

**0130-docker-secret/docker.default.secret_kubectl.yaml**

```shell
export docker_password=YOURDOCKERPASSWORD
```

**0320-k53certbot/0-zerossl.secret_kubectl.yaml**

```shell
export zerossl_api_key=YOURAPIKEY
```

## 4. Create infrastructure

```shell
ringmaster --debug stack up
```

_Relax while your stack is created_

```
                 .--.   ( ZZZZZZZZZZZZZZZZZZZZ! )
    ----------__/  u\u  /'-------------------------------------------
      `-'`-'  \ |(   C|
               \ \_  -'--.       `-'`-'`-'
                \|   . "-.\                      `-'`-'`-'
     `-'`-'`-'   \\ \______\\___
    --------------\\_____\)'--.-)----------------------------------
                /  \ / (  |    \ \
     VK        /    \__.`-|--\  \ \
              /__.--'     |   `. \__--.
             '            |     )___\--`
```

_Probably don't relax too hard at the moment, this is concept-level software ATM ;-)_

## 5. Customise the stack

You should now have working Kubernetes cluster, if you want to deploy your own
apps, your free to use regular `kubectl`, `helm` and then use `ringmaster` to
run these scripts or just run them manually.