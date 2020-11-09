#!/bin/bash
set -e
set -u

# create whole cluster and VPC if needed
if eksctl get cluster --region "$aws_region" "$cluster_name" &> /dev/null ; then
  echo "$msg_up_to_date"
else
  eksctl create cluster \
    --name "$cluster_name" \
    --version 1.18 \
    --region "$aws_region" \
    --vpc-nat-mode HighlyAvailable \
    --zones="$cluster_zones" \
    --with-oidc \
    --fargate
fi

# grab info about this cluster and put it in the databag
eksctl get cluster --region "$aws_region" "$cluster_name" --output json > "$eksctl_databag_file"

