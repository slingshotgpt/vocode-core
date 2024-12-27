import sys
from aws_config_params import *

# defaults if no command line args specified
env_type, inst_type = EnvType.dev, InstType.outbound

if "-inbound" in sys.argv:
    inst_type = InstType.inbound
if "-outbound" in sys.argv:
    inst_type = InstType.outbound
if "-prod" in sys.argv:
    env_type = EnvType.prod
if "-dev" in sys.argv:
    env_type = EnvType.dev

msg = f"*** Configured with {env_type} and {inst_type} ***"
print("*" * len(msg))
print(msg)
print("*" * len(msg))

# Load the correct configs for the situation, these are imported in other files
network_config: NetworkConfig
instance_config: InstanceConfig

match env_type:
    case EnvType.dev:
        network_config = NetworkDev
    case EnvType.prod:
        network_config = NetworkProd

match inst_type:
    case InstType.inbound:
        instance_config = InstanceInbound
    case InstType.outbound:
        instance_config = InstanceOutbound