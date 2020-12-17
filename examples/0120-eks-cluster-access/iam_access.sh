#!/bin/bash
# Add `eks_cluster_admin_arn` role as a system:masters RBAC user

VERB="$1"
if [ $VERB == $up_verb ] ; then
  if eksctl get iamidentitymapping \
      --region "$aws_region" \
      --cluster "$cluster_name" \
      --arn "$eks_cluster_admin_arn" ; then
    echo "$msg_up_to_date"
  else
    eksctl create iamidentitymapping \
      --region "$aws_region" \
      --cluster "$cluster_name" \
      --arn "$eks_cluster_admin_arn" \
      --group system:masters \
      --username admin
  fi
else
  echo "system going down - no action needed"
fi