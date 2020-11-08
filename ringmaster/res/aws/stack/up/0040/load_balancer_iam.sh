#!/bin/bash
set -e
set -u

policy_name=AWSLoadBalancerControllerIAMPolicy
policy_arn="arn:aws:iam::${aws_account_id}:policy/${policy_name}"
if aws iam get-policy --policy-arn "$policy_arn" > /dev/null ; then
  echo "$msg_up_to_date"
else
  aws iam create-policy \
      --policy-name "$policy_name" \
      --policy-document "file://iam_policy.json"
fi

# update the databag!
cat > "$intermediate_databag_file" <<EOF
{"aws_loadbalancer_controller_iam_policy_arn": "$policy_arn"}
EOF
