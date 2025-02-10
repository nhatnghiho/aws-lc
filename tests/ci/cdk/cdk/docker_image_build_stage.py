# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stage, aws_codebuild as codebuild, Environment, Stack, aws_iam as iam
from constructs import Construct

from cdk.ecr_stack import EcrStack
from cdk.linux_docker_image_batch_build_stack import LinuxDockerImageBatchBuildStack
from cdk.windows_docker_image_build_stack import WindowsDockerImageBuildStack
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class DockerImageBuildStage(Stage):
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

        # Define AWS ECR stacks.
        # ECR holds the docker images, which are pre-built to accelerate the code builds/tests of git pull requests.
        self.ecr_linux_x86_stack = EcrStack(
            self,
            "aws-lc-ecr-linux-x86",
            LINUX_X86_ECR_REPO,
            env=env,
            stack_name="aws-lc-ecr-linux-x86",
        )
        self.ecr_linux_aarch_stack = EcrStack(
            self,
            "aws-lc-ecr-linux-aarch",
            LINUX_AARCH_ECR_REPO,
            env=env,
            stack_name="aws-lc-ecr-linux-aarch",
        )
        self.ecr_windows_x86 = EcrStack(
            self,
            "aws-lc-ecr-windows-x86",
            WINDOWS_X86_ECR_REPO,
            env=env,
            stack_name="aws-lc-ecr-windows-x86",
        )

        # Define CodeBuild Batch job for building Docker images.
        self.linux_docker_build_stack = LinuxDockerImageBatchBuildStack(
            self,
            "aws-lc-docker-image-build-linux",
            env=env,
            stack_name="aws-lc-docker-image-build-linux",
        )
        self.linux_docker_build_stack.add_dependency(self.ecr_linux_x86_stack)
        self.linux_docker_build_stack.add_dependency(self.ecr_linux_aarch_stack)

        # self.windows_docker_build_stack = WindowsDockerImageBuildStack(
        #     self,
        #     "aws-lc-docker-image-build-windows",
        #     env=env,
        #     stack_name="aws-lc-docker-image-build-windows",
        # )
        # self.windows_docker_build_stack.add_dependency(self.ecr_windows_x86)

    @property
    def stacks(self):
        return [child.stack_name for child in self.node.children if isinstance(child, Stack)]


class SetupStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # In Account B
        cross_account_role = iam.Role(
            self,
            'CrossAccountCodeBuildRole',
            role_name='CrossAccountCodeBuildRole',
            # assumed_by=iam.PrincipalWithConditions(
            #     iam.AccountPrincipal(PIPELINE_ACCOUNT),
            #     {
            #         'StringEquals': {
            #             'aws:PrincipalArn': f'arn:aws:iam::{PIPELINE_ACCOUNT}:role/*CodeBuildActionRole*'
            #         }
            #     }
            # )
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

