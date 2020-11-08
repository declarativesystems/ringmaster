#!/bin/bash
set -e
set -u

# --name doesnt work...
aws_load_balancer_controller_service_name=aws-load-balancer-controller
if eksctl get iamserviceaccount  --cluster "$cluster_name" --region "$region" 2> /dev/null| grep -q "$aws_load_balancer_controller_service_name" ; then
  echo "$msg_up_to_date"
else
  eksctl create iamserviceaccount \
    --region="$region" \
    --cluster="$cluster_name" \
    --namespace=kube-system \
    --name="$aws_load_balancer_controller_service_name" \
    --attach-policy-arn="$aws_loadbalancer_controller_iam_policy_arn" \
    --override-existing-serviceaccounts \
    --approve
fi

cat > "$intermediate_databag_file" <<EOF
{"aws_load_balancer_controller_service_name": "$aws_load_balancer_controller_service_name"}
EOF