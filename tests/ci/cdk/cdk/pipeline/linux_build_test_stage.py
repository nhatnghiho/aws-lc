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
from util.metadata import LINUX_X86_ECR_REPO, LINUX_AARCH_ECR_REPO, WINDOWS_X86_ECR_REPO, AWS_ACCOUNT, AWS_REGION, \
    PIPELINE_ACCOUNT


class LinuxBuildTestStage(Stage):
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

        self.docker_stacks = [
            self.ecr_linux_x86_stack,
            self.ecr_linux_aarch_stack,
            self.linux_docker_build_stack
        ]

        # Define CodeBuild Batch job for testing code.
        x86_build_spec_file = "cdk/codebuild/github_ci_linux_x86_omnibus.yaml"
        self.ci_linux_x86_stack = AwsLcGitHubCIStack(
            self,
            "aws-lc-ci-linux-x86",
            x86_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-linux-x86",
        )
        self.ci_linux_x86_stack.add_dependency(self.linux_docker_build_stack)

        arm_build_spec_file = "cdk/codebuild/github_ci_linux_arm_omnibus.yaml"
        self.ci_linux_aarch_stack = AwsLcGitHubCIStack(
            self,
            "aws-lc-ci-linux-arm",
            arm_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-linux-arm",
        )
        self.ci_linux_aarch_stack.add_dependency(self.linux_docker_build_stack)

        integration_build_spec_file = "cdk/codebuild/github_ci_integration_omnibus.yaml"
        self.ci_integration_stack = AwsLcGitHubCIStack(
            self,
            "aws-lc-ci-integration",
            integration_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-integration",
        )
        self.ci_integration_stack.add_dependency(self.linux_docker_build_stack)

        fuzz_build_spec_file = "cdk/codebuild/github_ci_fuzzing_omnibus.yaml"
        self.ci_fuzzing_stack = AwsLcGitHubFuzzCIStack(
            self,
            "aws-lc-ci-fuzzing",
            fuzz_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-fuzzing",
        )
        self.ci_fuzzing_stack.add_dependency(self.linux_docker_build_stack)

        analytics_build_spec_file = "cdk/codebuild/github_ci_analytics_omnibus.yaml"
        self.ci_analytics_stack = AwsLcGitHubAnalyticsStack(
            self,
            "aws-lc-ci-analytics",
            analytics_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-analytics",
        )
        self.ci_analytics_stack.add_dependency(self.linux_docker_build_stack)

        # bm_framework_build_spec_file = "cdk/codebuild/bm_framework_omnibus.yaml"
        # BmFrameworkStack(app, "aws-lc-ci-bm-framework", bm_framework_build_spec_file, env=env)
        ec2_test_framework_build_spec_file = (
            "cdk/codebuild/ec2_test_framework_omnibus.yaml"
        )
        self.ci_ec2_test_framework_stack = AwsLcEC2TestingCIStack(
            self,
            "aws-lc-ci-ec2-test-framework",
            ec2_test_framework_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-ec2-test-framework",
        )
        self.ci_ec2_test_framework_stack.add_dependency(self.linux_docker_build_stack)

        android_build_spec_file = "cdk/codebuild/github_ci_android_omnibus.yaml"
        self.ci_android_stack = AwsLcAndroidCIStack(
            self,
            "aws-lc-ci-devicefarm-android",
            android_build_spec_file,
            env=env,
            stack_name="aws-lc-ci-devicefarm-android",
        )
        self.ci_android_stack.add_dependency(self.linux_docker_build_stack)

        self.ci_stacks = [
            self.ci_linux_x86_stack,
            self.ci_linux_aarch_stack,
            self.ci_integration_stack,
            self.ci_fuzzing_stack,
            self.ci_analytics_stack,
            self.ci_ec2_test_framework_stack,
            self.ci_android_stack
        ]

        self.docker_stack_names = [stack.stack_name for stack in self.docker_stacks]
        self.ci_stack_names = [stack.stack_name for stack in self.ci_stacks]
        self.step = None

    # @property
    # def stacks(self):
    #     return [child.stack_name for child in self.node.children if isinstance(child, Stack)]

    def add_stage_to_wave(
            self,
            wave: pipelines.Wave,
            input: pipelines.FileSet,
            role: iam.Role,
            name_prefix: str,
            env
    ):
        self.step = CodeBuildRunStep(
            f"{name_prefix}-CiTest",
            input=input,
            name_prefix=f"{name_prefix}-CiTest",
            stacks=[stack.stack_name for stack in self.ci_stacks],
            build_projects=[stack.stack_name for stack in self.ci_stacks],
            build_type="docker",
            platform="linux",
            env=env,
            role=role
        )

        wave.add_stage(
            self,
            stack_steps=[
                pipelines.StackSteps(
                    stack = self.linux_docker_build_stack,
                    post=[
                        CodeBuildRunStep(
                            f"{name_prefix}-LinuxDockerBuild",
                            input=input,
                            name_prefix=f"{name_prefix}-LinuxDockerBuild",
                            stacks=[stack.stack_name for stack in self.docker_stacks],
                            build_projects=["aws-lc-docker-image-build-linux"],
                            build_type="docker",
                            platform="linux",
                            env=env,
                            role=role
                        )
                    ]
                ),
            ],
            post=[
                self.step,
                # CodeBuildRunStep(
                #     f"{name_prefix}-CiTest",
                #     input=input,
                #     name_prefix=f"{name_prefix}-CiTest",
                #     stacks=[stack.stack_name for stack in self.ci_stacks],
                #     build_projects=[stack.stack_name for stack in self.ci_stacks],
                #     build_type="docker",
                #     platform="linux",
                #     env=env,
                #     role=role
                # )
            ]
        )

    # def docker_build_steps(
    #         self,
    #         name_prefix: str,
    #         role,
    # ):
    #     trigger_condition_check_step = pipelines.CodeBuildStep(
    #         "PrebuildCheck",
    #         commands=[
    #             "ls",
    #             "pwd",
    #             "cd tests/ci/cdk/cdk/scripts",
    #             "chmod +x trigger_condition_check.sh",
    #             "./trigger_condition_check.sh --build-type ${BUILD_TYPE} --platform ${PLATFORM} --stacks \"${STACKS}\"",
    #         ],
    #         role=role
    #     )
    #
    #     docker_build_step = pipelines.CodeBuildStep(
    #         "PrebuildCheck",
    #         commands=[
    #             "ls",
    #             "pwd",
    #             "cd tests/ci/cdk/cdk/scripts",
    #             "chmod +x trigger_condition_check.sh",
    #             "./trigger_condition_check.sh --build-type ${BUILD_TYPE} --platform ${PLATFORM} --stacks \"${STACKS}\"",
    #         ],
    #         role=role,
    #         project_name=f"{self.name_prefix}-CodeBuildStartWait"
    #     )
    #
    #     docker_build_step.add_step_dependency(trigger_condition_check_step)
    #
    #     return pipelines.Step.sequence([
    #         trigger_condition_check_step,
    #         docker_build_step,
    #     ])
