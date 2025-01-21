import subprocess
import time 
import signal 
import sys
import argparse
import os

def run_command(command):
    """Run a shell command in a non-blocking subprocess."""
    std_out = subprocess.PIPE
    std_err = subprocess.PIPE
    if "redis-server" in command and is_redis_running():
        print("Redis is already running, skipping...")
        return None 
    if "ngrok" in command and is_ngrok_running():
        print("ngrok is already running, skipping...")
        return None
    if "uvicorn" in command and is_uvicorn_running():
        print("Uvicorn is already running, skipping...")
        return None
    if "uvicorn" in command: 
        std_out = sys.stdout
        std_err = sys.stderr

    return subprocess.Popen(command, shell=True, stdout=std_out, stderr=std_err)

def is_redis_running():
    """Check if redis-server is already running."""
    try: 
        subprocess.check_output("redis-cli ping", shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def is_ngrok_running():
    """Check if ngrok is already running."""
    try:
        output = subprocess.check_output("pgrep -f 'ngrok http'", shell=True)
        return bool(output)
    except subprocess.CalledProcessError:
        return False

def is_uvicorn_running():
    """Check if Uvicorn is already running."""
    try:
        output = subprocess.check_output("pgrep -f 'uvicorn'", shell=True)
        return bool(output)
    except subprocess.CalledProcessError:
        return False

# Handle termination
def terminate_processes(signum, frame):
    print("\nTerminating all processes...")
    for process in processes:
        process.terminate()
        process.wait()
    print("All processes terminated.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Start services for telephony application.")
    parser.add_argument("--call_type", choices=["inbound", "outbound"], default="inbound", help="Specify call type: inbound or outbound.")
    parser.add_argument("--language", choices=["en", "kr"], default="en", help="Specify language: English, Korean")
    args = parser.parse_args()

    global commands
    commands = [
        "ngrok http --url=slingshotgpt.ngrok.app 3000",
        "redis-server",
        f"uvicorn telephony_{args.call_type}:app --host 0.0.0.0 --port 3000"
    ]

    # set global variable
    os.environ["LANGUAGE"] = args.language

    # Start subprocesses
    for cmd in commands:
        print(f"Starting: {cmd}")
        proc = run_command(cmd)
        if proc:
            processes.append(proc) 

    # Attach signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, terminate_processes)
    signal.signal(signal.SIGTERM, terminate_processes)

    # Monitor processes
    try:
        while True:
            for i, process in enumerate(processes):
                retcode = process.poll()
                if retcode is not None:
                    print(f"Process {commands[i]} exited with code {retcode}")
                    processes[i] = run_command(commands[i])
                    print(f"Restarted: {commands[i]}")
            time.sleep(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        terminate_processes(None, None)

if __name__ == "__main__":
    processes = []
    main()