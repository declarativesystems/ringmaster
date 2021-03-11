# Ringmaster
```
         _
       _[_]_
       _(_)______.-'`-.
      /, >< ,----'     `-._.-'*
      \\|::|  Welcome to the Circus
        |/\|  We already got enough Clowns,
        ||||  You got any experiance with
        ||||  Being shot from a canon??
     __(_/\_)
    /`-..__.,-'\
   /   __/\__   \
   `._ \    / _.'MJP
      ``|/\|-'
```

Ringmaster organises a bunch of other tools on your behalf so that you don't
have to. The aim is you can create, updated and delete entire stacks crossing
cloudformation, EKS, kubectl, helm and random Python/BASH scripts with a single
command.

Ringmaster helps you create and share your automation scripts with others, so
you can get up and running as quick as possible. There are no agents, hubs, 
gits or daemons - unless you add them yourself. 

There is also no custom DSL or new programming language to learn, although
[jinja2](https://jinja.palletsprojects.com/) is used for templating.

Ringmaster is just files on a disk and calls to other systems made in an order
you decide.

## How does it work?

You create a directory of scripts to process, like this:

```
stack/
├── 0010-iam
│     ├── AWSLoadBalancerController.iam_policy.json
│     ├── Certbot.iam_policy.json
│     ├── EksDeploy.iam_policy.json
│     ├── EksExternalSecrets.iam_policy.json
│     ├── ExternalDns.iam_policy.json
│     └── metadata.yaml
├── 0020-efs
│     ├── efs.cloudformation.yaml
│     └── metadata.yaml
├── 0030-vpc
│     ├── metadata.yaml
│     ├── vpc.remote_cloudformation.yaml
│     └── vpc.yaml
...
```

Then you run `ringmaster` like this:

`ringmaster stack up`

Ringmaster will carry out the _create_ action of each script, running each 
script in alphabetical order by _directory_ and then _file_

`ringmaster stack down`

Ringmaster will carry out the delete action of each script, in _reverse_
alphabetical order

**The `up` and `down` actions are 
[idempotent](https://en.wikipedia.org/wiki/Idempotence#Computer_science_examples)
so you can run them as many times as you like**


## What's in the scripts? do I have to learn a new language?

No! The scripts use the languages and tools you already know and love, eg:

* Cloudformation
* Bash
* Python
* Kubernetes deployment descriptors
* ...etc

Ringmaster uses a [databag](doc/concepts.md#databag) to give each script the
right inputs and collects outputs that may be required later. Combined with a
simple built-in variable substitution system, this makes gluing completely 
different systems together easy, eg:

```
cloudformation -> ekscl -> more cloudformation -> heml -> kubectl -> ...
```

To reduce dependency on ringmaster and allow easy debugging and repeatable
deployments, substitution results are stored adjacent to their input files, so
they can be added to git or use directly by tools such as `kubectl`.

## Reference

1. [Concepts](doc/concepts.md)
2. [Setup](doc/setup.md)
3. [Authentication](doc/authentication.md)
4. [Handlers](doc/handlers.md)
5. [Scripts](doc/scripts.md)
6. [Variables](doc/variables.md)   
7. [Worked Example](doc/worked_example.md)
