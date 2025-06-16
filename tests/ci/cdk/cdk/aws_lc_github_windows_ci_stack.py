import typing

from aws_cdk import (
    aws_codebuild as codebuild,
    aws_iam as iam,
    Environment,
)
from constructs import Construct

from cdk.aws_lc_github_ci_stack import AwsLcGitHubCIStack
from util.iam_policies import (
    ecr_power_user_policy_in_json,
)
from util.metadata import WINDOWS_X86_ECR_REPO


class AwsLcGitHubWindowsCIStack(AwsLcGitHubCIStack):
    def __init__(
            self,
            scope: Construct,
            id: str,
            spec_file_path: str,
            env: typing.Union[Environment, typing.Dict[str, typing.Any]],
            **kwargs
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            spec_file_path=spec_file_path,
            env=env,
            **kwargs
        )

        self.role.attach_inline_policy(iam.Policy(
            self,
            "ecr_power_user_policy",
            document=iam.PolicyDocument.from_json(ecr_power_user_policy_in_json([WINDOWS_X86_ECR_REPO], env))
        ))

        inline_policies = {
            "ecr_power_user_policy": iam.PolicyDocument.from_json(ecr_power_user_policy_in_json([WINDOWS_X86_ECR_REPO], env))
        }
        fleet_service_role = iam.Role(
            scope=self,
            id="test-fleet-role",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies=inline_policies,
        )

        compute_fleet = codebuild.CfnFleet(
            self,
            "aws_lc_windows_2019_64_core_cdk",
            base_capacity=1,
            compute_type="CUSTOM_INSTANCE_TYPE",
            compute_configuration=codebuild.CfnFleet.ComputeConfigurationProperty(
                disk=64,
                memory=128,
                v_cpu=64,
            ),
            environment_type="WINDOWS_SERVER_2019_CONTAINER",
            fleet_service_role=fleet_service_role.role_name,
            name="aws_lc_windows_2019_64_core_cdk"
        )