Audit-Logger
============

Audit Logger is a lightweight, python based log auditing tool designed to help system admins get a better handle on various logs
distributes accross various filesystem and system locations.

Audit Logger supports monitoring of log files, indexing of the individual log messages within each file, and the relational storage of
log messages associated by user defined criteria.

Additionally AL exposes a CL query interface, designed so that admins can perform a relational lookup of the logs given particular terms
specified in setup.

Currently only logs formatted in JSON are supported, but support for more formats, including custom formats, may be forthcoming.

Setup
-----

Setting up Audit Logger is fairly straight forward, and requires only a toml file.

This TOML file demands two components, a description of the log files to be audited,
and how they should be indexed for auditing and stored after audit on the host file system.

The first requirement, the log layout, should be specified by the form:

```
[logs]
root = "/tmp/gitlab-development-environment"
    [logs.<name>]
    ext = "log"
    log_prefix = "gitlab/log/"
    log_names = [
                    "importer",
                    "auth",
                    "development_json",
                    "gettext",
                    "grpc",
                    "api_json",
                    "sidekiq_client",
                    "application_json",
                    "development",
                    "service_measurement",
                    "exceptions_json",
                    "graphql_json",
                    "audt_json",
                    "git_json",
                ]
    format = "json"

    [logs.<name>]
    ext = "log"
    log_prefix = "log/praefect-gitaly-0/"
    log_names = [
                    "gitaly_hooks",
                    "gitlay_ruby_json"
                ]
    format = "json"

```
Where a filesystem location must be specified as a root for the log files (although each sub log can override this)
as the `root` variable, and each grouping must designate a format, an extension, and a series of names.

The second component of the config defines how the logs will be indexed for searching and eventually stored.
The user must specify a root level relational key (or keys) that will be used to index each log event being audited,
the attribute that will be used to specify the event (and therefore the key) and how that attribute will be identified.
The options for this are either by file or by log attribute.

Each sub grouping therein relates the parsed log messages by an attribute. In the example below, schema.project.pipeline relates
log messages by their associated project, and pipeline, with that order of precedence.

```
[schema]
key = "application_json.log"
key_type = "file"
relator = "correlation_id"
    [schema.project]
    lookup = ["project_id"]
        [schema.project.pipeline]
            lookup = ["pipeline_id"]
            [schema.project.pipeline.job]
            lookup = ["job_id", "runner_id"]
```

An example of a toml file exists at audit-logger/test/ex_conf.toml


Audit logger also provides a simple CLI with four basic commands.

Start - starts audit logger, requires a `--config` arg denoting the config toml file described above.
Stop - stops audit logger and performs cleanup
Status - gives status of audit logger process
C - command form, allows user to issue auditing queries of the logs based on the attributes specified in the schema.
    Output is piped to stdout of process issuing command.
    Queries are of the form: `Q key=val;key2=val2` or `Q schema_relator=<val>`


Notice
======
There are some small active developments being made in the name of performance (particularly surrouding querying)

Further, the query interface is by no means final, and is currently built to serve as a first pass proof of concept with a more
sophisticated lookup interface being the end goal, driven by user feedback.
