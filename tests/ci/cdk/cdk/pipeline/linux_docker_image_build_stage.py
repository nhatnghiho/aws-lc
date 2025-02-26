# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stage, aws_codebuild as codebuild, Environment, Stack, aws_iam as iam, pipelines
from constructs import Construct

from cdk.aws_lc_analytics_stack import AwsLcGitHubAnalyticsStack
from cdk.aws_lc_android_ci_stack import AwsLcAndroidCIStack
from cdk.aws_lc_ec2_test_framework_ci_stack import AwsLcEC2TestingCIStack
from cdk.aws_lc_github_ci_stack import AwsLcGitHubCIStack
from cdk.aws_lc_github_fuzz_ci_stack import AwsLcGitHubFuzzCIStack
from cdk.ecr_stack import EcrStack
from cdk.linux_docker_image_batch_build_stack import LinuxDockerImageBatchBuildStack
from cdk.pipeline.codebuild_run_step import CodeBuildRunStep
from cdk.pipeline.deploy_util import DeployEnvironmentType
from cdk.pipeline.docker_build_step import DockerBuildStep
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class LinuxDockerImageBuildStage(Stage):
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

        # Define AWS ECR stacks.
        # ECR holds the docker images, which are pre-built to accelerate the code builds/tests of git pull requests.
        self.ecr_linux_x86_stack = EcrStack(
            self,
            "aws-lc-ecr-linux-x86",
            LINUX_X86_ECR_REPO,
            env=env,
            stack_name="aws-lc-ecr-linux-x86"
        )
        self.ecr_linux_aarch_stack = EcrStack(
            self,
            "aws-lc-ecr-linux-aarch",
            LINUX_AARCH_ECR_REPO,
            env=env,
            stack_name="aws-lc-ecr-linux-aarch"
        )

        # Define CodeBuild Batch job for building Docker images.
        self.linux_docker_build_stack = LinuxDockerImageBatchBuildStack(
            self,
            "aws-lc-docker-image-build-linux",
            env=env,
            stack_name="aws-lc-docker-image-build-linux"
        )
        self.linux_docker_build_stack.add_dependency(self.ecr_linux_x86_stack)
        self.linux_docker_build_stack.add_dependency(self.ecr_linux_aarch_stack)

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
            additional_stacks: list[Stack]=[],
            env=None,
    ):
        stacks = self.stacks + additional_stacks

        wave.add_stage(
            self,
            post=[
                DockerBuildStep(
                    f"{deploy_environment.value}-LinuxDockerBuild",
                    input=input,
                    name_prefix=f"{deploy_environment.value}-Linux",
                    stacks=[stack.stack_name for stack in stacks],
                    platform="linux",
                    max_retry=max_retry,
                    env=env,
                    role=role
                )
            ]
        )

