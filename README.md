# Tooling for Maven

This repository contains tooling that makes using Maven for large sets of loosely dependent projects easier.


## Description

The commands follow `mvn-ext-*` naming pattern. Following commands are available:

* `mvn-ext-each`: finds all Maven projects by their POM files and possibly generates a reactor POM for all found projects
* `mvn-ext-print`: prints the output of an interpolation template executed in a Maven project


## Prerequisites

* Bash
* Maven
* Python 3.7 or newer


## Installation

It must be possible to launch Python using `python3` command. This is not the case of the default Windows installation, but it can be fixed; the easiest way is making an alias for `python.exe`, e.g., by running `mklink python3.exe python.exe` in Python installation directory (which requires Administrator privileges when adjusting the installation for all users).


## Running

The preferred way of running all the tools, including those with the core implemented in Python, is launching the provided shell scripts. On Windows it means using MSYS2 environment, which is bundled with Git installation, so it is usually no problem. It is quite a good idea to put the directory with the scripts to the `PATH`.

All commands provide `-h` or `--help` options to display usage details.

