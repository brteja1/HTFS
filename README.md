# HTFS – Hierarchically Tagged File System
A tag-driven filesystem organization tool that allows you to assign hierarchical tags (tags with parent-child relationships, like an ontology) to any file or folder.
HTFS makes it easy to organize, search, and retrieve files beyond the limitations of traditional folder-only structures, using tags that form a DAG and can have multiple parents.

# Features
* **Hierarchical Tags** – Create and manage tags with parent/child relationships, including tags with multiple parents (e.g., Project > Alpha > Reports).
* **Multi-Tag Support** – Assign multiple tags to a file or directory.
* **Powerful Searching** – Query files by tags, including all descendants of a tag.
* **Cross-Platform** – Works on Linux, macOS, and Windows.
* **Command-Line Interface** – Fast, scriptable workflows for developers, researchers, and system admins.
* **Ontology-Like Organization** – Organize content the way you think, not just where it’s stored.
* **Automatic Tracking** – Optional daemon to track file moves and renames automatically (Linux).

# How It Works
HTFS stores tag metadata separately from the filesystem hierarchy, enabling:
* Multiple categorization for the same file
* Tags can live in a DAG, so a tag may have more than one parent
* Hierarchical searches that adapt to real-world classification
* Compatibility with existing folder structures

# Installation

## Requirements
- **Python** 3.7+

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/youruser/HTFS.git
   cd HTFS
   ```

2. **Install the package**:
   ```bash
   # Core installation
   pip install .

   # Or for development (editable mode)
   pip install -e .
   ```

3. **(Optional) Install with Daemon Support** (Linux only):
   This enables the `tagfs-daemon` for automatic filesystem event tracking.
   ```bash
   pip install ".[daemon]"
   ```

# Usage

## Quick Start

1. **Initialize** a tagfs database in your desired directory:
   ```bash
   cd /path/to/your/data
   tagfs init
   ```
   This creates `.tagfs.db` (SQLite) and `.tagfs.ttl` (RDF) files to store your metadata.

2. **Manage Tags**:
   ```bash
   # Create tags with hierarchy (using / as separator)
   tagfs addtags "Project/Alpha/Design" "Project/Alpha/Development"

   # Link existing tags
   tagfs linktags "Research" "Project"
   ```

3. **Tag Resources**:
   ```bash
   # Track and tag a file
   tagfs addresource ./file.pdf
   tagfs tagresource ./file.pdf Design Research
   tagfs untagresource ./file.pdf Design Research
   tagfs untagresource ./file.pdf --all
   ```
   Hierarchical resource tags must already exist as valid tag paths. If the hierarchy is incomplete or incorrect, the command fails with an invalid tag error.
   Use `rmresourcetags` only as a legacy alias for `untagresource --all`.

4. **Query**:
   ```bash
   # Query files by tags (boolean expressions with &, |, ~)
   tagfs lsresources "Project&Development"
   tagfs lsresources "(Design|Development)&~Draft"

   # List tags on a resource
   tagfs getresourcetags ./file.pdf

   # Export the HTFS graph as Graphviz DOT
   tagfs exportgraph -o graph.dot

   # Render it with Graphviz
   dot -Tpng graph.dot -o graph.png
   ```

## Running the Daemon (Linux)
To automatically track file moves and renames within your tagfs boundary:
```bash
tagfs-daemon /path/to/your/data &
```

## Commands Reference
For a full list of commands:
```bash
tagfs help
```
The `exportgraph` command writes the tag/resource graph in Graphviz DOT format. Use `-o/--output` to save it to a file, or omit it to print to stdout.

# Architecture

    +------------+       +-------------------+       +----------------+
    |  CLI Tool  |  -->  |  Tagging Engine   |  -->  | Metadata Store |
    +------------+       +-------------------+       +----------------+
           ↑                       |                   (SQLite + RDF)
           └-------->  File System <------------ External Scripts

# Use Cases
* **Research Papers**: Organize by topic hierarchy (Science/Biology/Genetics) and status (ToRead/Reading/Completed).
* **Project Management**: Track assets across multiple overlapping categories and project phases.
* **Digital Archives**: Tag large collections for better retrieval without moving physical files.
