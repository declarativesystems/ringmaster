# Setup

## Prerequisites
_Install and configure_:

* AWS CLI v2 with IAM admin rights on your AWS account
* eksctl
* kubectl
* helm v3
* Python 3 + pip

**You must use EKS compatible versions!** 
https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html 

_Optional but highly recommended_:

* A nice editor
* git

## Ringmaster

```shell
pip install ringmaster.show

# test it works...
ringmaster --version
```