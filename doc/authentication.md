# Authentication

## AWS

This is handled directly by the 
[Boto3 API](https://aws.amazon.com/sdk-for-python/) which uses the files in 
`~/.aws` to configure credentials.

The default _profile_ will be used automatically, use the `AWS_PROFILE` 
environment variable to use a different one:

```
AWS_PROFILE="someprofile" ringmaster ...
```

All work is done inside a single region which is controlled by databag value:
```
aws_region: "us-east-1" # eg
```

## Kubernetes

**[ringmaster uses the active kubectl context](https://github.com/declarativesystems/ringmaster/issues/1)**

As eksctl sets up a cluster, it configures the active kubectl context which
ringmaster will then use.

**If you manage other clusters set the active context before running 
ringmaster**
 
## Snowflake

Configure your credentials in `~/.ringmaster/snowflake.yaml`:

```yaml
credentials:
  user: "yourusername"
  password: "t0ps3re4!"
  account: "XX11111.ap-southeast-2"
```

