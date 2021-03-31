import ringmaster.aws as aws


def test_filename_to_stackname():
    """cloudformation stack naming"""
    stackname = aws.filename_to_stack_name("someproject/stack/0010-vpc/vpc.cloudformation.yaml")
    assert stackname == "vpc"