import enum
import os 

class EnvType(enum.Enum):
    dev = 1
    prod = 2
    
class NetworkDev:
    ENVIRONMENT = EnvType.prod
    REGION = "us-west-2"
    BASE_URL = "dialers.slingshotgpt.com"

    VPC_ID = "vpc-0261970c0228c0b9e"
    PRIVATE_SUBNET_IDS = [
        "subnet-08c05605ea336c0e5",
        "subnet-08a707b4ed8324e65",
        "subnet-0535eeb95dc1c9cc4"
    ]
    PUBLIC_SUBNET_IDS = [
        "subnet-04c820a1386471426",
        "subnet-0c15d1d4413818df7",
        "subnet-0e72c7acdc6ba4419"
    ]
    SECURITY_GROUPS = ["sg-07116857dba014f11"]

class NetworkProd:
    ENVIRONMENT = EnvType.prod
    REGION = "us-west-2"
    BASE_URL = "dialers.slingshotgpt.com"

    VPC_ID = "vpc-0261970c0228c0b9e"
    PRIVATE_SUBNET_IDS = [
        "subnet-08c05605ea336c0e5",
        "subnet-08a707b4ed8324e65",
        "subnet-0535eeb95dc1c9cc4"
    ]
    PUBLIC_SUBNET_IDS = [
        "subnet-04c820a1386471426",
        "subnet-0c15d1d4413818df7",
        "subnet-0e72c7acdc6ba4419"
    ]
    SECURITY_GROUPS = ["sg-07116857dba014f11"]


NetworkConfig = NetworkProd | NetworkDev

class SharedConfig:
    AWS_ID = "149536473922"
    TARGET_BASENAME = "slingshot-tg-"
    INSTANCE_BASENAME = "instance"
    INSTANCES_PER_LB = 95


class InstType(enum.Enum):
    outbound = 1
    inbound = 2


class InstanceInbound(SharedConfig):
    INSTANCE_TYPE = InstType.inbound
    URL_EXT = "inbound"
    ECR_INSTANCE = "slingshot-inbound-prod"
    TASKNAME_INSTANCE = "slingshot-inbound-prod:{tag}"
    LOAD_BALANCER_BASENAME = "slingshot-prod-lb"
    SERVICE_NAME = "slingshot-inbound-prod"
    CLUSTER = "slingshot-inbound-prod"


class InstanceOutbound(SharedConfig):
    INSTANCE_TYPE = InstType.outbound
    URL_EXT = "outbound"
    ECR_INSTANCE = "slingshot-outbound-prod"
    TASKNAME_INSTANCE = "slingshot-outbound-prod:{tag}"
    LOAD_BALANCER_BASENAME = "slingshot-outbound-lb"
    SERVICE_NAME = "slingshot-outbound-prod"
    CLUSTER = (
        "test-cluster"
        if os.environ.get("TEST_CLUSTER")
        else "slingshot-outbound-instances"
    )


InstanceConfig = InstanceInbound | InstanceOutbound

class ConfigGen:
    @classmethod
    def config_service_new(
        cls,
        network_config: NetworkConfig,
        instance_config: InstanceConfig,
        desired_count: int,
        service_name: str,
        tag: str = "3",
    ):
        subnets = (
            network_config.SIP_PUBLIC_SUBNET_IDS
            if network_config.ENVIRONMENT == EnvType.dev
            else network_config.PRIVATE_SUBNET_IDS
        )
        security_groups = (
            network_config.SIP_SECURITY_GROUPS
            if network_config.ENVIRONMENT == EnvType.dev
            else network_config.SECURITY_GROUPS
        )
        aws_vpc_configuration = {
            "subnets": subnets,
            "securityGroups": security_groups,
        }
        if network_config.ENVIRONMENT == EnvType.dev:
            aws_vpc_configuration["assignPublicIp"] = "ENABLED"

        return {
            "cluster": instance_config.CLUSTER,
            "serviceName": service_name,
            "desiredCount": desired_count,
            "taskDefinition": instance_config.TASKNAME_INSTANCE.format(tag=tag),
            "launchType": "FARGATE",
            "enableExecuteCommand": True,
            "networkConfiguration": {"awsvpcConfiguration": aws_vpc_configuration},
        }

    @classmethod
    def config_service_update(
        cls,
        instance_config: InstanceConfig,
        desired_count: int,
        service_name: str,
    ):
        return {
            "service": service_name,
            "cluster": instance_config.CLUSTER,
            "desiredCount": desired_count,
        }

    @classmethod
    def config_target_group(
        cls,
        network_config: NetworkConfig,
        tg_name: str,
    ):
        return {
            "Name": tg_name,
            "Protocol": "HTTP",
            "Port": 80,
            "VpcId": network_config.VPC_ID,
            "TargetType": "ip",
            "HealthyThresholdCount": 2,
            "UnhealthyThresholdCount": 2,
            "HealthCheckIntervalSeconds": 300,
            "HealthCheckTimeoutSeconds": 60,
            "Matcher": {"HttpCode": "200,404"},
        }

    @classmethod
    def config_register_target(
        cls,
        tg_arn: str,
        ip: str,
    ):
        return {
            "TargetGroupArn": tg_arn,
            "Targets": [
                {
                    "Id": ip,
                    "Port": 80,
                }
            ],
        }

    @classmethod
    def config_rule(cls, listener_arn: str, tg_arn: str, url: str, priority: int):
        return {
            "ListenerArn": listener_arn,
            "Priority": priority,
            "Conditions": [
                {
                    "Field": "host-header",
                    "Values": [url],
                }
            ],
            "Actions": [
                {
                    "Type": "forward",
                    "TargetGroupArn": tg_arn,
                }
            ],
        }