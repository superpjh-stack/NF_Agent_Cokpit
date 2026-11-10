import os

import aws_cdk as cdk

from stack import NeedsFoodV2WebStack


app = cdk.App(outdir=os.getenv("CDK_OUTDIR", "cdk.out"))
NeedsFoodV2WebStack(app, "NeedsFoodV2Web", env=cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "ap-northeast-2"),
))
app.synth()
