import subprocess
import sys
from config import instance_config, network_config

USAGE = """
Usage: python slingshot-aws/build_push.py (-dev | -prod) (-inbound | -outbound)
(run in the parent directory of slingshot-aws)
"""

def run_command(command):
    """
    Executes a shell command and handles errors.

    Args:
        command (str): The shell command to execute.

    Returns:
        bool: True if the command runs successfully, False otherwise.
    """
    try:
        subprocess.check_call(command, shell=True)
        return True
    except subprocess.CalledProcessError as error:
        print(f"Error executing command: {command}")
        print(error)
        print("\n" + "*" * 26)
        print("*** BUILD NOT FINISHED ***")
        print("*" * 26)
        return False

def build(directory, ecr_repository, tag):
    """
    Builds, tags, and pushes a Docker image to AWS ECR.

    Args:
        directory (str): The directory containing the Dockerfile.
        ecr_repository (str): The ECR repository name.
        tag (str): The Docker image tag.
    """
    aws_account_id = instance_config.AWS_ID
    aws_region = network_config.REGION
    ecr_url = f"{aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com"
    dockerfile_path = f"{directory}/Dockerfile.{instance_config.URL_EXT}"
    commands = [
        f"aws ecr get-login-password --region {aws_region} | docker login --username AWS --password-stdin {ecr_url}",
        #f"docker build --platform=linux/arm64 -f {dockerfile_path} -t {ecr_repository}:{tag} .",
        f"docker build --platform=linux/amd64 -f {dockerfile_path} -t {ecr_repository}:{tag} .",
        f"docker tag {ecr_repository}:{tag} {ecr_url}/{ecr_repository}:{tag}",
        f"docker push {ecr_url}/{ecr_repository}:{tag}",
    ]
    for command in commands:
        if not run_command(command):
            print(USAGE)
            break

if __name__ == "__main__":
    # Default tag is 'latest' unless specified via command-line arguments
    tag = "latest"
    if "-tag" in sys.argv:
        try:
            tag_index = sys.argv.index("-tag") + 1
            tag = sys.argv[tag_index]
        except IndexError:
            print("Error: No tag value provided after '-tag'")
            print(USAGE)
            sys.exit(1)

    print(f"Tagging image with: {tag}")
    build("slingshot-aws", instance_config.ECR_INSTANCE, tag)