## Local run
# inbound local run
- python bin/run_local.py
# outbound local run
- python bin/run_local.py --call_type=outbound

## Cloud deploy
# inbound aws deploy
- python slingshot-aws/build_push.py -prod -inbound
# outbound aws deploy
- python slingshot-aws/build_push.py -prod -outbound