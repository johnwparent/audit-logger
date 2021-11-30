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

An example of a toml file exists at audit-logger/test/ex_conf.toml
