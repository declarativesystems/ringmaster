#!/bin/bash
set -e
if eksctl get cluster --region "$region" "$cluster_name" &> /dev/null ; then
  eksctl delete cluster --region "$region" "$cluster_name"
else
  echo "[√] up to date"
fi