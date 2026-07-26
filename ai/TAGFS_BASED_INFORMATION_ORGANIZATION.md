# TagFS-Based Information Organization & Query Expectations

This document outlines the guidelines for AI agents regarding information organization, knowledge retrieval, and content ingestion within the workspace using the Hierarchically Tagged File System (`tagfs`).

## 1. Information Organization & Expansion

*   **Tag-based Documentation**: When introducing new concepts, create a chapter in `wiki/`, register it with `/path/to/HTFS/bin/tagfs addresource <path>`, and add appropriate tags with `/path/to/HTFS/bin/tagfs tagresource <path> <tags...>`.
*   **Knowledge Base Expansion**: If a user's query cannot be answered using the local `wiki/` pages and requires searching the source code or the web, you must summarize the newly discovered information into a new `wiki/` page. Register and tag this new page using `tagfs` so that future queries on the topic can be answered locally.

## 2. Query Expectations

*   **Efficient Knowledge Retrieval**: When answering questions, always check local `wiki/` pages first before searching sources or the web. To conserve tokens, never `grep` the wiki directory. Instead, infer relevant tags from the user's query, use `/linuxdev/github/HTFS/bin/tagfs lsresources <tags>` to locate the specific files, and read only those. Keep responses concise.

## 3. Wiki Content & Ingestion Requirements

When adding or maintaining documentation wiki files in `wiki/`, always adhere to the following clean-room processing guidelines:

1.  **No Bite-Sized Content**: Information must be kept comprehensive and textbook-like. Retain Automatic Differentiation and Enzyme modules.
2.  **Hierarchical Taxonomy**: Ensure tag structures are fully hierarchical. Enable multi-parent tag associations to properly organize interdisciplinary topics (e.g. `ssa` parented to both `ir` and `optimization`).
3.  **Boilerplate & Credit Stripping**: Keep only structural, conceptual, and development-oriented content. Always strip off sections containing:
    *   Credits, contributor tables, license copyrights (e.g. `&#169; Copyright` or `© Copyright`), and authorship lists.
    *   Sphinx website template navigation bars, footer signatures, upcoming release tags, and YQL JavaScript news scrapers.
4.  **Verbatim/Absolute Link Mappings**: 
    *   Map offline-available relative HTML links to their corresponding local `.md` file paths (e.g. `file:///.../wiki/polly/passes.md`).
    *   Preserve external and un-downloaded relative links by rewriting them to their **absolute online source URLs** (e.g., resolving `genindex.html` to `https://polly.llvm.org/docs/genindex.html`) so navigation is never broken.
5.  **Code Block Annotations**: Analyze all code snippets inside documentation and annotate code blocks with their explicit programming language format (such as ````llvm````, ````cpp````, ````bash````, ````dot````) to ensure correct syntax highlighting.
6.  **Authoritative References**: Maintain a centralized `wiki/sources/` index file listing the primary academic research papers, specs, and books used to compile the handbook chapters. Whenever a new external source (web URL, local PDF, manual, or textbook) is given or ingested, document it properly under this sources section.
7.  **Text Formatting & Paragraph Spacing**: Preserve natural paragraph wrapping. Do not inject hard line breaks (`\n\n`) on every line, letting text wrap smoothly according to the container's width.
