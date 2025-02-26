# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stack, Environment
from aws_cdk import (
    pipelines,
    aws_codestarconnections as codestarconnections,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
)
from aws_cdk.aws_s3_assets import Asset
from aws_cdk.pipelines import CodeBuildStep
from constructs import Construct

from cdk.pipeline.ci_stage import CiStage
from cdk.pipeline.codebuild_run_step import CodeBuildRunStep
from cdk.pipeline.linux_build_test_stage import LinuxBuildTestStage
from cdk.pipeline.setup_stage import SetupStage
from cdk.pipeline.windows_build_test_stage import WindowsBuildTestStage
from util.metadata import (
    AWS_ACCOUNT,
    AWS_REGION,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    GITHUB_SOURCE_VERSION, PIPELINE_ACCOUNT, PIPELINE_REGION,
)


class AwsLcCiPipeline(Stack):
    def __init__(
            self,
            scope: Construct,
            id: str,
            **kwargs,
    ) -> None:
        super().__init__(
            scope,
            id,
            **kwargs,
        )

        gh_connection = codestarconnections.CfnConnection(
            self,
            "GitHubConnection",
            connection_name="AwsLcCiPipelineGitHubConnection",
            provider_type="GitHub",
        )

        cross_account_role = iam.Role(
            self,
            "CrossAccountCodeBuildRole",
            role_name="CrossAccountCodeBuildRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("codebuild.amazonaws.com"),
                iam.ServicePrincipal("codepipeline.amazonaws.com")
            ),
        )

        cross_account_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=[f'arn:aws:iam::{AWS_ACCOUNT}:role/CrossAccountCodeBuildRole'],
                actions=["sts:AssumeRole"],
            )
        )

        cross_account_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=['*'],
                actions=["codepipeline:GetPipelineExecution"],
            )
        )

        source = pipelines.CodePipelineSource.connection(
            f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}",
            "ci-pipeline",
            connection_arn=gh_connection.attr_connection_arn,
            code_build_clone_output=True,
        )

        commit_hash = source.source_attribute("CommitId")

        # Creating a base pipeline to override the default execution mode
        code_pipeline = codepipeline.Pipeline(
            self,
            "BasePipeline",
            execution_mode=codepipeline.ExecutionMode.QUEUED,
            pipeline_type=codepipeline.PipelineType.V2,
            pipeline_name="AwsLcCiPipeline",
            cross_account_keys=True
        )

        pipeline = pipelines.CodePipeline(
            self,
            "AwsLcCiPipeline",
            code_pipeline=code_pipeline,
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "echo \"Environment variables:\"",
                    "env",
                    "npm install -g aws-cdk",
                    "cd tests/ci",
                    "python -m pip install -r requirements.txt",
                    "cd cdk",
                    "cdk synth"
                ],
                env={
                    "CDK_DEPLOY_ACCOUNT": AWS_ACCOUNT,
                    "CDK_DEPLOY_REGION": AWS_REGION,
                    "GITHUB_REPO_OWNER": GITHUB_REPO_OWNER,
                    "GITHUB_REPO_NAME": GITHUB_REPO_NAME,
                    "GITHUB_SOURCE_VERSION": GITHUB_SOURCE_VERSION,
                    "PIPELINE_ACCOUNT": PIPELINE_ACCOUNT,
                    "PIPELINE_REGION": PIPELINE_REGION,
                    "PRE_PROD_ACCOUNT": AWS_ACCOUNT,
                    "PRE_PROD_REGION": AWS_REGION,
                    "COMMIT_HASH": commit_hash
                },
                primary_output_directory="tests/ci/cdk/cdk.out",
            ),
            self_mutation=True,
            code_build_defaults=pipelines.CodeBuildOptions(
                role_policy=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        actions=["sts:AssumeRole"],
                        conditions={
                            "StringEquals": {
                                "iam:ResourceTag/aws-cdk:bootstrap-role": "lookup",
                            }
                        }
                    ),
                ],
                build_environment=codebuild.BuildEnvironment(
                    environment_variables={
                        "PIPELINE_ACCOUNT": codebuild.BuildEnvironmentVariable(value=PIPELINE_ACCOUNT),
                        "PIPELINE_REGION": codebuild.BuildEnvironmentVariable(value=PIPELINE_REGION),
                        "PRE_PROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=AWS_ACCOUNT),
                        "PRE_PROD_REGION": codebuild.BuildEnvironmentVariable(value=AWS_REGION),
                        # "GITHUB_REPO_OWNER": codebuild.BuildEnvironmentVariable(value=GITHUB_REPO_OWNER),
                        # "GITHUB_REPO_NAME": codebuild.BuildEnvironmentVariable(value=GITHUB_REPO_NAME),
                        # "GITHUB_SOURCE_VERSION": codebuild.BuildEnvironmentVariable(value=GITHUB_SOURCE_VERSION),
                    }
                ),
            )
        )

        setup_stage = SetupStage(
            self,
            "Setup",
            env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        )

        # pipeline.add_stage(setup_stage)

        test_step = pipelines.CodeBuildStep(
            "TestStep",
            commands=[
                # "build_id=$(aws codebuild start-build-batch --project-name aws-lc-docker-image-build-linux | jq -r '.buildBatch.id')",
                # "export AWS_LC_LINUX_BUILD_BATCH_ID='${build_id}'"
                "env",
            ],
            input=source,
            env={
                # "STACKS": docker_image_build_stage.stacks,
                "COMMIT_HASH": commit_hash
            },
            role=cross_account_role
        )

        test_step_2 = pipelines.CodeBuildStep(
            "TestStep2",
            commands=[
                # "build_id=$(aws codebuild start-build-batch --project-name aws-lc-docker-image-build-linux | jq -r '.buildBatch.id')",
                # "export AWS_LC_LINUX_BUILD_BATCH_ID='${build_id}'"
                "env",
            ],
            input=source,
            env={
                # "STACKS": docker_image_build_stage.stacks,
                "COMMIT_HASH": commit_hash
            },
            role=cross_account_role
        )

        test_wave = pipeline.add_wave("TestWave")
        test_wave.add_stage(
            setup_stage,
            post=[test_step]
        )

        linux_stage = LinuxBuildTestStage(
            self,
            "Staging-LinuxBuildTest",
            env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        )

        # linux_stage.add_stage_to_wave(
        #     wave=test_wave,
        #     input=source.primary_output,
        #     role=cross_account_role,
        #     name_prefix="Staging",
        #     env={
        #         "PIPELINE_EXECUTION_ID": "#{codepipeline.PipelineExecutionId}",
        #         "COMMIT_HASH": commit_hash,
        #         "DEPLOY_ACCOUNT": AWS_ACCOUNT,
        #         "DEPLOY_REGION": AWS_REGION
        #     },
        # )

        # test_step.add_step_dependency(linux_stage.step)

        name_prefix = "Staging"

        step = CodeBuildRunStep(
            f"{name_prefix}-CiTest",
            input=source.primary_output,
            name_prefix=f"{name_prefix}-CiTest",
            stacks=[stack.stack_name for stack in linux_stage.ci_stacks],
            build_projects=[stack.stack_name for stack in linux_stage.ci_stacks],
            build_type="docker",
            platform="linux",
            env={
                "PIPELINE_EXECUTION_ID": "#{codepipeline.PipelineExecutionId}",
                "COMMIT_HASH": commit_hash,
                "DEPLOY_ACCOUNT": AWS_ACCOUNT,
                "DEPLOY_REGION": AWS_REGION
            },
            role=cross_account_role
        )

        test_wave.add_stage(
            linux_stage,
            # stack_steps=[
            #     pipelines.StackSteps(
            #         stack = linux_stage.linux_docker_build_stack,
            #         post=[
            #             CodeBuildRunStep(
            #                 f"{name_prefix}-LinuxDockerBuild",
            #                 input=source.primary_output,
            #                 name_prefix=f"{name_prefix}-LinuxDockerBuild",
            #                 stacks=[stack.stack_name for stack in linux_stage.docker_stacks],
            #                 build_projects=["aws-lc-docker-image-build-linux"],
            #                 build_type="docker",
            #                 platform="linux",
            #                 env={
            #                     "PIPELINE_EXECUTION_ID": "#{codepipeline.PipelineExecutionId}",
            #                     "COMMIT_HASH": commit_hash,
            #                     "DEPLOY_ACCOUNT": AWS_ACCOUNT,
            #                     "DEPLOY_REGION": AWS_REGION
            #                 },
            #                 role=cross_account_role
            #             )
            #         ]
            #     ),
            # ],
            post=[
                test_step_2
            ]
        )

        test_step.add_step_dependency(test_step_2)

        windows_stage = WindowsBuildTestStage(
            self,
            "Staging-WindowsBuildTest",
            env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        )

        test_wave.add_stage(windows_stage)

        # pipeline.add_stage(
        #     linux_stage,
        #     post=[
        #         # CodeBuildStep(
        #         #     "StartDockerBuild",
        #         #     commands=[
        #         #         # "build_id=$(aws codebuild start-build-batch --project-name aws-lc-docker-image-build-linux | jq -r '.buildBatch.id')",
        #         #         # "export AWS_LC_LINUX_BUILD_BATCH_ID='${build_id}'"
        #         #         "ls",
        #         #         "pwd",
        #         #         "cd tests/ci/cdk/cdk/scripts",
        #         #         "chmod +x codebuild_start_wait.sh",
        #         #         f"./codebuild_start_wait.sh --stacks \"{' '.join(docker_image_build_stage.stacks)}\""
        #         #     ],
        #         #     input=source,
        #         #     env={
        #         #         # "STACKS": docker_image_build_stage.stacks,
        #         #         "COMMIT_HASH": commit_hash
        #         #     },
        #         #     role=cross_account_role
        #         # ),
        #         CodeBuildRunStep(
        #             "StartDockerBuild",
        #             input=source,
        #             name_prefix="Staging",
        #             stacks=linux_stage.stacks,
        #             build_projects=["aws-lc-docker-image-build-linux"],
        #             build_type="docker",
        #             platform="linux",
        #             env={
        #                 "PIPELINE_EXECUTION_ID": "#{codepipeline.PipelineExecutionId}",
        #                 "COMMIT_HASH": commit_hash,
        #                 "DEPLOY_ACCOUNT": AWS_ACCOUNT,
        #                 "DEPLOY_REGION": AWS_REGION
        #             },
        #             role=cross_account_role
        #         ),
        #         CodeBuildRunStep(
        #             "StartDockerBuild-Test",
        #             input=source,
        #             name_prefix="Staging",
        #             stacks=linux_stage.stacks,
        #             build_projects=["aws-lc-docker-image-build-linux"],
        #             build_type="docker",
        #             platform="linux",
        #             env={
        #                 "PIPELINE_EXECUTION_ID": "#{codepipeline.PipelineExecutionId}",
        #                 "COMMIT_HASH": commit_hash,
        #                 "DEPLOY_ACCOUNT": AWS_ACCOUNT,
        #                 "DEPLOY_REGION": AWS_REGION
        #             },
        #             role=cross_account_role
        #         )
        #     ]
        # )

        # ci_stage = CiStage(
        #     self,
        #     "Staging-CiStage",
        #     env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        # )

        # pipeline.add_stage(
        #     ci_stage,
        #     post=[
        #         CodeBuildStep(
        #             "RunIntegrationTests",
        #             commands=[
        #                 "echo \"Environment variables:\"",
        #                 "env",
        #             ],
        #             role=cross_account_role
        #         ),
        #     ]
        # )

        pipeline.build_pipeline()

        # Schedule pipeline to run every Tuesday 15:00 UTC or 7:00 PST
        events.Rule(
            self, "WeeklyCodePipelineTrigger",
            schedule=events.Schedule.cron(
                minute="0",
                hour="15",
                # weekday="TUE", #TODO: Uncomment this line. It's running everyday right now to make sure I didn't break anything
            ),
            targets=[
                targets.CodePipeline(
                    pipeline=pipeline.pipeline
                )
            ]
        )


