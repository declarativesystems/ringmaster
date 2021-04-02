import ringmaster.aws as aws


def test_filename_to_stackname():
    """cloudformation stack naming"""
    stackname = aws.filename_to_stack_name("someproject/stack/0010-vpc/vpc.cloudformation.yaml")
    assert stackname == "vpc"


def test_eks_name_to_kubectl_context_id():
    context_id = aws.eks_name_to_kubectl_context_id(
        "iam.user",
        "foo-dev",
        "us-east-1",
    )
    assert context_id == "iam.user@foo-dev.us-east-1.eksctl.io"