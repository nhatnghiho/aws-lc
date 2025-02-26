from aws_cdk import Stage, aws_codebuild as codebuild, Environment, Stack, aws_iam as iam
from constructs import Construct

from cdk.ecr_stack import EcrStack
from cdk.linux_docker_image_batch_build_stack import LinuxDockerImageBatchBuildStack
from cdk.windows_docker_image_build_stack import WindowsDockerImageBuildStack
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class SetupStage(Stage):
    def __init__(
            self,
            scope: Construct,
            id,
            **kwargs
    ):
        super().__init__(
            scope,
            id,
            **kwargs,
        )

        env=Environment(account=AWS_ACCOUNT, region=AWS_REGION)

        self.setup_stack = SetupStack(
            self,
            "aws-lc-pipeline-setup",
            env=env,
            stack_name="aws-lc-pipeline-setup",
        )

class SetupStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        cross_account_role = iam.Role(
            self,
            'CrossAccountCodeBuildRole',
            role_name='CrossAccountCodeBuildRole',
            assumed_by=iam.ArnPrincipal(f'arn:aws:iam::{PIPELINE_ACCOUNT}:role/CrossAccountCodeBuildRole') #TODO: add a conditional to exclude this in dev env,
        )

        # Grant access to all CodeBuild projects
        cross_account_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'codebuild:StartBuild',
                'codebuild:StartBuildBatch',
                'codebuild:BatchGetBuilds',
                'codebuild:StopBuild',
                'codebuild:ListProjects',  # Add permission to list projects
                'codebuild:BatchGetProjects'  # Add permission to get project details
            ],
            resources=[f'arn:aws:codebuild:{AWS_REGION}:{AWS_ACCOUNT}:project/aws-lc-*']
        ))

        cross_account_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                'cloudformation:DescribeChangeSet',
                'cloudformation:DescribeStacks'
            ],
            resources=['*']
        ))