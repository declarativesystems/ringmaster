# Scripts

Ringmaster supports scripts using any of the supported [handlers](handlers.md).

There are two ways to get your scripts:

1. Download them from [examples](examples) using `ringmaster get`
2. Create your own [scripts](doc/scripts.md)

## Downloading

`ringmaster` has built-in support for downloading and verifying scripts. 

To download scripts:

```shell
ringmaster get STACK_DIR/LOCAL_DIR https://url.directory
```

_eg_:

```shell
ringmaster get stack/0010-iam https://raw.githubusercontent.com/declarativesystems/ringmaster/examples/0010-iam
```

_Would create:_

```
0010-iam/
├── AWSLoadBalancerController.iam_policy.json
├── Certbot.iam_policy.json
├── EksDeploy.iam_policy.json
├── EksExternalSecrets.iam_policy.json
├── ExternalDns.iam_policy.json
└── metadata.yaml

```

* Make sure to give the link to the `raw` version of your script if using github
* You can change the local directory if you like
* `metadata.yaml` must exist as a child of `url.directory`
* `metadata.yaml` contains a list of files to download and their hashes
* Local edits will abort the download process to prevent accidental overwriting

## Creating

1. Find the [stack](concepts.md#stacks) directory you want your script to
   belong to or create a new one
2. Create a directory for your script to run in. Numbering the directory is an
   easy way to get your script to run in the right order
3. Write your script - since you already know cloudformation, Bash, Python,
   Kubernetes deployment descriptors and a bunch of other stuff, you already
   know how to do this, so just make sure the filename of your script matches
   the handler you want to use.
   
   Some scripts support variable substitution, so you do things like have your
   Kubernetes deployment descriptors automatically rewritten for you, other 
   scripts such as cloudformation will do an automatic parameter lookup from 
   the databag. The best way to get started is look at the 
   [handlers](handlers.md) documentation and the existing examples.
   
## Sharing

If you've written a cool script and want to share it with the World, all you
need to do is generate your metadata and publish to the internet.

**Generating metadata**

```shell
ringmaster metadata DIRECTORY
```

_eg_

```shell
ringmaster metadata my_stack/0300-some-cool-thing
```

* Create `my_stack/0300-some-cool-thing/metadata.yaml`
* List all files inside `my_stack/0300-some-cool-thing` with matching handlers
  in the `files` section
* Set the `name` field to `0300-some-cool-thing`
* Create a `description` field for you to fill out if you like

If you have additional files that form part of the script use the `--include`
argument. 

_At the moment `name` and `description` are for your own reference._

To publish your script, upload the whole directory somewhere, eg github.

Now anyone with access to the URL can use the script.