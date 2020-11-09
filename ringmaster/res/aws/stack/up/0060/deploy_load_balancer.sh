#!/bin/bash
set -e
set -u

if kubectl get deployment -n kube-system "$aws_load_balancer_controller_service_name" &> /dev/null ; then
  echo "$msg_up_to_date"
else

  # fixme - do something with helm

  # repo for more random shit
  helm repo add eks https://aws.github.io/eks-charts

  # https://github.com/kubernetes-sigs/aws-load-balancer-controller/issues/1561
  helm upgrade -i aws-load-balancer-controller eks/aws-load-balancer-controller \
    --set clusterName="$cluster_name" \
    --set serviceAccount.create=false \
    --set serviceAccount.name="$aws_load_balancer_controller_service_name" \
    --set region="$aws_region" --set vpcId="$resourcesvpcconfig_vpcid" \
    -n kube-system

  # wait a while, say the special prayer:
  # >   "Ancient Spirits of Evil,
  # >   Transform this decayed form,
  # >   to Mumm-Ra, the Ever-Living!"
fi