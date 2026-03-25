# HTFS – Hierarchically Tagged File System
A tag-driven filesystem organization tool that allows you to assign hierarchical tags (tags with parent-child relationships, like an ontology) to any file or folder.
HTFS makes it easy to organize, search, and retrieve files beyond the limitations of traditional folder-only structures.

# Features
* Hierarchical Tags – Create and manage tags with parent/child relationships (e.g., Project > Alpha > Reports).
* Multi-Tag Support – Assign multiple tags to a file or directory.
* Powerful Searching – Query files by tags, including all descendants of a tag.
* Cross-Platform – Works on Linux, macOS, and Windows.
* Command-Line Interface – Fast, scriptable workflows for developers, researchers, and system admins.
* Ontology-Like Organization – Organize content the way you think, not just where it’s stored.

# How It Works
HTFS stores tag metadata separately from the filesystem hierarchy, enabling:
* Multiple categorization for the same file
* Hierarchical searches that adapt to real-world classification
* Compatibility with existing folder structures

# Architecture

    +------------+       +-------------------+       +----------------+
    |  CLI Tool  |  -->  |  Tagging Engine   |  -->  | Metadata Store |
    +------------+       +-------------------+       +----------------+
           ↑                       |
           └-------->  File System <------------ External Scripts

# Use Cases
* Organizing research papers by topic hierarchy (Science/Biology/Genetics)
* Managing project assets across multiple overlapping categories
* Automating log file categorization for system administration
* Tagging large digital archives for better retrieval


# Installation & Dependencies

## Requirements

### Core Dependencies
- **Python** 3.7+
- **rdflib** (>= 6.0) – RDF graph management and SPARQL query execution
  ```bash
  pip install rdflib
  ```

### Optional Dependencies
- **inotify** – For automatic filesystem event tracking (Linux only)
  ```bash
  pip install inotify
  ```

## Setup

1. Install core dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Install additional features:
   ```bash
   pip install -r requirements-optional.txt
   ```
   This enables the inotify daemon for automatic filesystem event tracking.

3. Initialize a tagfs database in your desired directory:
   ```bash
   cd /path/to/your/data
   tagfs init
   ```
   This creates a `.tagfs.ttl` file that stores all tag hierarchies and file associations in RDF format.

# Usage

## Quick Start

```bash
# View available commands
tagfs help

# Create tags with hierarchy (using / as separator)
tagfs addtags "Project/Alpha/Design" "Project/Alpha/Development"

# Track a file
tagfs addresource /path/to/file.pdf

# Assign tags to file
tagfs tagresource /path/to/file.pdf Design "Project"

# Query files by tags (boolean expressions with &, |, ~)
tagfs lsresources "Project&Development"
tagfs lsresources "(Design|Development)&~Draft"

# List tags on a resource
tagfs getresourcetags /path/to/file.pdf
```

## Commands Reference

For detailed command usage:
```bash
tagfs help
```
