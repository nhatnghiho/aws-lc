# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stage, aws_codebuild as codebuild, Environment, Stack, aws_iam as iam
from constructs import Construct

from cdk.ecr_stack import EcrStack
from cdk.windows_docker_image_build_stack import WindowsDockerImageBuildStack
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class WindowsBuildTestStage(Stage):
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

        self.ecr_windows_x86 = EcrStack(
            self,
            "aws-lc-ecr-windows-x86",
            WINDOWS_X86_ECR_REPO,
            env=env,
        )

        # self.windows_docker_build_stack = WindowsDockerImageBuildStack(
        #     self,
        #     "aws-lc-docker-image-build-windows",
        #     env=env,
        #     stack_name="aws-lc-docker-image-build-windows",
        # )
        # self.windows_docker_build_stack.add_dependency(self.ecr_windows_x86)