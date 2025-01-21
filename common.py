import os
import boto3
import sys
import json

from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager

config_manager = RedisConfigManager()

SECRETS = ['slingshotgpt_vocode_credentials']

def get_secret(secret_name, region_name='us-west-2'):
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in response:
            secret = response['SecretString']
        else:
            # Secrets can also be stored as binary
            secret = response['SecretString'].decode('utf-8')
        
        return json.loads(secret) if secret.strip().startswith('{') else secret

    except client.exceptions.ResourceNotFoundException:
        print(f"The requested secret {secret_name} was not found.")
    except client.exceptions.InvalidRequestException as e:
        print(f"The request was invalid: {e}")
    except client.exceptions.InvalidParameterException as e:
        print(f"The request had invalid params: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")    