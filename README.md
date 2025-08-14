# HTFS – Hierarchically Tagged File System
A tag-driven filesystem organization tool that allows you to assign hierarchical tags (tags with parent-child relationships, like an ontology) to any file or folder.
HTFS makes it easy to organize, search, and retrieve files beyond the limitations of traditional folder-only structures.

# Features
    Hierarchical Tags – Create and manage tags with parent/child relationships (e.g., Project > Alpha > Reports).
    Multi-Tag Support – Assign multiple tags to a file or directory.
    Powerful Searching – Query files by tags, including all descendants of a tag.
    Cross-Platform – Works on Linux, macOS, and Windows (limitations may apply for extended attributes).
    Command-Line Interface – Fast, scriptable workflows for developers, researchers, and system admins.
    Ontology-Like Organization – Organize content the way you think, not just where it’s stored.

# How It Works
HTFS stores tag metadata separately from the filesystem hierarchy, enabling:

    Multiple categorization for the same file
    Hierarchical searches that adapt to real-world classification
    Compatibility with existing folder structures

# Architecture
+------------+       +-------------------+       +----------------+
|  CLI Tool  |  -->  |  Tagging Engine   |  -->  | Metadata Store |
+------------+       +-------------------+       +----------------+
       ↑                       |
       └-------->  File System <------------ External Scripts

# Use Cases
    Organizing research papers by topic hierarchy (Science/Biology/Genetics)
    Managing project assets across multiple overlapping categories
    Automating log file categorization for system administration
    Tagging large digital archives for better retrieval


# Usage
tagfs help - will provide the details on how to use the utility.
