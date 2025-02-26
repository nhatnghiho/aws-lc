# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stage, aws_codebuild as codebuild, Environment, Stack, aws_iam as iam, pipelines
from constructs import Construct

from cdk.ecr_stack import EcrStack
from cdk.pipeline.codebuild_run_step import CodeBuildRunStep
from cdk.pipeline.deploy_util import DeployEnvironmentType
from cdk.pipeline.docker_build_step import DockerBuildStep
from cdk.windows_docker_image_build_stack import WindowsDockerImageBuildStack
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class WindowsDockerImageBuildStage(Stage):
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
            stack_name="aws-lc-ecr-windows-x86"
        )

        # self.windows_docker_build_stack = WindowsDockerImageBuildStack(
        #     self,
        #     "aws-lc-docker-image-build-windows",
        #     env=env,
        #     stack_name="aws-lc-docker-image-build-windows",
        # )
        # self.windows_docker_build_stack.add_dependency(self.ecr_windows_x86)

    @property
    def stacks(self):
        return [child for child in self.node.children if isinstance(child, Stack)]

    def add_stage_to_wave(
            self,
            wave: pipelines.Wave,
            input: pipelines.FileSet,
            role: iam.Role,
            deploy_environment: DeployEnvironmentType,
            max_retry: int=2,
            additional_stacks: list[Construct]=[],
            env=None,
    ):
        stacks = self.stacks + additional_stacks

        wave.add_stage(
            self,
            post=[
                DockerBuildStep(
                    f"{deploy_environment.value}-WindowsDockerBuild",
                    input=input,
                    name_prefix=f"{deploy_environment.value}-Windows",
                    stacks=[stack.stack_name for stack in stacks],
                    platform="windows",
                    max_retry=max_retry,
                    env=env,
                    role=role
                )
            ]
        )