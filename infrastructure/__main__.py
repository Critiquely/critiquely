"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws

# Create an AWS resource (S3 Bucket)
ecr = aws.ecr.Repository("critique_engine",
    name="critique_engine",
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={
        "scan_on_push": True,
    })

# Export the name of the bucket
pulumi.export('ecr_url', ecr.repository_url)
