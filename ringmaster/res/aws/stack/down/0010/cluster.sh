#!/bin/bash
set -e
if eksctl get cluster --region "$aws_region" "$cluster_name" &> /dev/null ; then
  eksctl delete cluster --region "$aws_region" "$cluster_name"
else
  echo "[√] up to date"
fi