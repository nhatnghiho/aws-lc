# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC
from typing import Mapping

import jsii
from aws_cdk import (pipelines,
                     aws_codepipeline_actions as cp_actions,
                     aws_codebuild as codebuild,
                     aws_codepipeline as codepipeline
                    )

@jsii.implements(pipelines.ICodePipelineActionFactory)
class CodeBuildRunStep(pipelines.Step):
    def __init__(self,
                 id,
                 name_prefix,
                 # input: pipelines.IFileSetProducer,
                 input: pipelines.FileSet,
                 build_type,
                 platform,
                 stacks,
                 build_projects,
                 role,
                 max_retry: int=0,
                 env: dict[str, any]=None):
        super().__init__(id)

        self._discover_referenced_outputs({
            "env": {}
        })

        self.name_prefix = name_prefix
        self.input = input
        self.build_type = build_type
        self.platform = platform
        self.stacks = stacks
        self.build_projects = build_projects
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
                "phases": {
                    "build": {
                        "commands": [
                            "ls",
                            "pwd",
                            "cd tests/ci/cdk/cdk/pipeline/scripts",
                            "chmod +x trigger_condition_check.sh",
                            "./trigger_condition_check.sh --build-type ${BUILD_TYPE} --platform ${PLATFORM} --stacks \"${STACKS}\""
                        ]
                    }
                }
            }),
            role=self.role,
            project_name=f"{self.name_prefix}-TriggerConditionCheck"
        )

        codebuild_start_wait_project = codebuild.PipelineProject(
            scope,
            f"{self.name_prefix}-StartWait",
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "build": {
                        "commands": [
                            "cd tests/ci/cdk/cdk/pipeline/scripts",
                            "chmod +x codebuild_start_wait.sh",
                            "./codebuild_start_wait.sh --build-type ${BUILD_TYPE} --platform ${PLATFORM} --project ${PROJECT} --max-retry ${MAX_RETRY}"
                        ]
                    }
                }
            }),
            role=self.role,
            project_name=f"{self.name_prefix}-StartWait"
        )

        stage.add_action(
            cp_actions.CodeBuildAction(
                action_name=f"{self.name_prefix}-PrebuildCheck",
                # input=artifacts.to_code_pipeline(self.input.primary_output),
                input=artifacts.to_code_pipeline(self.input),
                run_order=run_order,
                project=trigger_condition_check_project,
                environment_variables={
                    "STACKS": codebuild.BuildEnvironmentVariable(value=" ".join(self.stacks)),
                    "BUILD_TYPE": codebuild.BuildEnvironmentVariable(value=self.build_type),
                    **self.env,
                },
                outputs=[codepipeline.Artifact()],
                variables_namespace=f'{self.name_prefix}-TriggerConditionCheck'
            )
        )

        # project="aws-lc-docker-image-build-linux"
        #
        # stage.add_action(
        #     cp_actions.CodeBuildAction(
        #         action_name=f"{project}.Build",
        #         input=artifacts.to_code_pipeline(self.input.primary_output),
        #         run_order=run_order + 1,
        #         project=codebuild_start_wait_project,
        #         environment_variables={
        #             "PROJECT": codebuild.BuildEnvironmentVariable(value=project),
        #             "MAX_RETRY": codebuild.BuildEnvironmentVariable(value=self.max_retry),
        #             "NEED_REBUILD": codebuild.BuildEnvironmentVariable(value=f'#{self.name_prefix}-TriggerConditionCheck.NEED_REBUILD'),
        #             **self.env
        #         },
        #     )
        # )

        for project in self.build_projects:
            stage.add_action(
                cp_actions.CodeBuildAction(
                    action_name=f"{project}.Build",
                    # input=artifacts.to_code_pipeline(self.input.primary_output),
                    input=artifacts.to_code_pipeline(self.input),
                    run_order=run_order + 1,
                    project=codebuild_start_wait_project,
                    environment_variables={
                        "BUILD_TYPE": codebuild.BuildEnvironmentVariable(value=self.build_type),
                        "PLATFORM": codebuild.BuildEnvironmentVariable(value=self.platform),
                        "PROJECT": codebuild.BuildEnvironmentVariable(value=project),
                        "MAX_RETRY": codebuild.BuildEnvironmentVariable(value=self.max_retry),
                        "NEED_REBUILD": codebuild.BuildEnvironmentVariable(value=f'#{self.name_prefix}-TriggerConditionCheck.NEED_REBUILD')
                    },
                )
            )

        return pipelines.CodePipelineActionFactoryResult(
            run_orders_consumed=2  # Because you're using two run orders (run_order and run_order + 1)
        )
