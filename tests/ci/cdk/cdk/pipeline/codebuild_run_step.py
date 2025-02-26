# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC
import re
from typing import Mapping

import jsii
from aws_cdk import (
    pipelines,
    aws_codepipeline_actions as cp_actions,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_iam as iam
)


class BatchBuildTargetOptions:
    def __init__(
            self,
            target: str,
            identifier: str = None,
            ignore_failure: bool = False,
            timeout: int = 180,
            env: Mapping[str, str] = {}
    ):
        self.target = target
        self.identifier = identifier or re.sub(r'[^a-zA-Z0-9]', '_', target)
        self.ignore_failure = ignore_failure
        self.timeout = timeout
        self.env = env

@jsii.implements(pipelines.ICodePipelineActionFactory)
class CodeBuildRunStep(pipelines.Step):
    def __init__(self,
                 id,
                 name_prefix,
                 # input: pipelines.IFileSetProducer,
                 input: pipelines.FileSet,
                 stacks: list[str],
                 role: iam.Role,
                 platform: str = "",
                 build_targets: list[BatchBuildTargetOptions] = None,
                 max_retry: int = 0,
                 env: Mapping[str, str] = {}):
        super().__init__(id)

        # self._discover_referenced_outputs({
        #     "env": {}
        # })

        self.name_prefix = name_prefix
        self.input = input
        self.platform = platform
        self.stacks = stacks
        self.build_targets = build_targets
        self.role = role
        self.max_retry = max_retry
        self.env = {
            key: codebuild.BuildEnvironmentVariable(value=value)
            for key, value in env.items()
        }

    @jsii.member(jsii_name="produceAction")
    def produce_action(self,
                       stage: codepipeline.IStage,
                       *,
                       scope,
                       action_name,
                       run_order,
                       variables_namespace=None,
                       artifacts: pipelines.ArtifactMap,
                       fallbackArtifact=None,
                       pipeline: pipelines.CodePipeline,
                       codeBuildDefaults=None,
                       beforeSelfMutation=None,
                       stack_outputs_map: pipelines.StackOutputsMap):
        trigger_condition_check_project = codebuild.PipelineProject(
            scope,
            f"{self.name_prefix}-TriggerConditionCheck",
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "env": {
                    "exported-variables": [
                        "NEED_REBUILD"
                    ]
                },
                "phases": {
                    "build": {
                        "commands": [
                            "cd tests/ci/cdk/cdk/pipeline/scripts",
                            "chmod +x trigger_condition_check.sh",
                            "./trigger_condition_check.sh --build-type ci --stacks \"${STACKS}\""
                        ]
                    }
                },
            }),
            role=self.role,
            project_name=f"{self.name_prefix}-TriggerConditionCheck"
        )

        batch_build_jobs = [
            {
                "identifier": options.identifier.replace('-', '_'),
                "ignore-failure": options.ignore_failure,
                "env": {
                    "variables": {
                        "PROJECT": options.target,
                        "TIMEOUT": options.timeout,
                        **options.env,
                    }
                }
            }
            for options in self.build_targets
        ]

        build_target_project = codebuild.PipelineProject(
            scope,
            f"{self.name_prefix}-StartWait",
            build_spec=codebuild.BuildSpec.from_object({
                "version": 0.2,
                "batch": {
                    "build-list": batch_build_jobs
                },
                "phases": {
                    "build": {
                        "commands": [
                            "cd tests/ci/cdk/cdk/pipeline/scripts",
                            "chmod +x build_target.sh",
                            "./build_target.sh --build-type ci \
                                                 --project ${PROJECT} \
                                                 --max-retry ${MAX_RETRY} \
                                                 --timeout ${TIMEOUT}"
                        ]
                    }
                }
            }),
            role=self.role,
            project_name=f"{self.name_prefix}-StartWait"
        )

        # test_project = codebuild.PipelineProject.from_project_arn(
        #     scope,
        #     f"{self.name_prefix}-Test",
        #     project_arn="arn:aws:codebuild:us-west-2:183295444613:project/aws-lc-ci-integration"
        # )
        #
        # dummy_artifact = codepipeline.Artifact()

        prebuild_check_action = cp_actions.CodeBuildAction(
            action_name=f"{self.name_prefix}-PrebuildCheck",
            # input=artifacts.to_code_pipeline(self.input.primary_output),
            input=artifacts.to_code_pipeline(self.input),
            run_order=run_order,
            project=trigger_condition_check_project,
            environment_variables={
                **self.env,
                "PLATFORM": codebuild.BuildEnvironmentVariable(value=self.platform),
                "STACKS": codebuild.BuildEnvironmentVariable(value=" ".join(self.stacks)),
            },
            outputs=[codepipeline.Artifact()],
            variables_namespace=f'{self.name_prefix}-TriggerConditionCheck',
        )

        stage.add_action(prebuild_check_action)


        build_target_action = cp_actions.CodeBuildAction(
            action_name=f"{self.name_prefix}-StartWait",
            # input=artifacts.to_code_pipeline(self.input.primary_output),
            input=artifacts.to_code_pipeline(self.input),
            run_order=run_order + 1,
            project=build_target_project,
            execute_batch_build=True,
            environment_variables={
                **self.env,
                "PLATFORM": codebuild.BuildEnvironmentVariable(value=self.platform),
                "MAX_RETRY": codebuild.BuildEnvironmentVariable(value=self.max_retry),
                "NEED_REBUILD": codebuild.BuildEnvironmentVariable(
                    value=f"#{{{self.name_prefix}-TriggerConditionCheck.NEED_REBUILD}}")
            },
        )

        stage.add_action(build_target_action)

        # for project in self.build_projects:
        #     build_target_action = cp_actions.CodeBuildAction(
        #         action_name=f"{self.name_prefix}-{project}.Build",
        #         # input=artifacts.to_code_pipeline(self.input.primary_output),
        #         input=artifacts.to_code_pipeline(self.input),
        #         run_order=run_order + 1,
        #         project=build_target_project,
        #         environment_variables={
        #             **self.env,
        #             "PLATFORM": codebuild.BuildEnvironmentVariable(value=self.platform),
        #             "PROJECT": codebuild.BuildEnvironmentVariable(value=project),
        #             "MAX_RETRY": codebuild.BuildEnvironmentVariable(value=self.max_retry),
        #             "NEED_REBUILD": codebuild.BuildEnvironmentVariable(value=f'#{self.name_prefix}-TriggerConditionCheck.NEED_REBUILD')
        #         },
        #     )
        #
        #     stage.add_action(build_target_action)

        # stage.add_action(
        #     cp_actions.CodeBuildAction(
        #         action_name=f"{self.name_prefix}-TestAction",
        #         # input=artifacts.to_code_pipeline(self.input.primary_output),
        #         # input=artifacts.to_code_pipeline(self.input),
        #         input=dummy_artifact,
        #         run_order=run_order+1,
        #         project=test_project,
        #     )
        # )

        return pipelines.CodePipelineActionFactoryResult(
            run_orders_consumed=2
        )
