# HTFS: Hierarchically Tagged File System
## Technical Design Document

**Version**: 1.0  
**Date**: 26 March 2026  
**System**: HTFS - A Hierarchical Tag-driven File Organization System

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Data Model & Ontology](#data-model--ontology)
5. [API & Interfaces](#api--interfaces)
6. [Query Processing Pipeline](#query-processing-pipeline)
7. [Storage & Persistence](#storage--persistence)
8. [Design Patterns](#design-patterns)
9. [Use Cases & Workflows](#use-cases--workflows)
10. [Performance Considerations](#performance-considerations)
11. [Future Extensions](#future-extensions)

---

## Executive Summary

HTFS is an innovative file organization system that decouples tagging from traditional filesystem hierarchies. The system enables:

- **Hierarchical Tags**: Tags organized in multiple parent-child relationships forming a directed acyclic graph (DAG)
- **Multi-tag Assignment**: Files and directories can have multiple tags across the hierarchy
- **Transitive Queries**: Searching by parent tags automatically includes all children in results
- **SPARQL-based Querying**: Complex tag expressions evaluated through RDF/SPARQL
- **CLI-driven Workflow**: Command-line interface for scripting and automation
- **Filesystem Integration**: Optional inotify daemon for automatic resource tracking on changes

### Key Innovation
Unlike traditional folders (which form a strict tree hierarchy), HTFS tags form a **hierarchical graph** where each tag can have multiple parents. When searching for a parent tag, the system automatically includes all descendant tags in the results, enabling intuitive, real-world classification schemes.

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                   CLI Layer (tagfs.py)              │
│  Commands: init, lstags, addtags, linktags, etc.    │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│           Utilities Layer (TagfsUtilities.py)       │
│  • Hierarchical tag handling                        │
│  • Resource normalization & management              │
│  • Tag expression evaluation                        │
│  • Filesystem boundary detection                    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼─────────┐  ┌────────▼────────────────┐
│  TagService.py  │  │ QueryEvaluator.py       │
│  • High-level   │  │ • AST Parser            │
│    Tag/Resource │  │ • Query Compilation     │
│    operations   │  │ • RDF/SPARQL bridge     │
└───────┬─────────┘  └────────┬────────────────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────────────────┐
        │DatabaseManager.py (Coordinator) │
        │ • SQLiteHandler.py (tag/resource)│
        │ • RDFHandler.py (tag/resource)   │
        └──────────┬───────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │   Storage Layer                   │
        │   • .tagfs.db (SQLite tables)     │
        │   • .tagfs.ttl (RDF Turtle file)  │
        └─────────────────────────────────┘
```

### Component Interaction Flow

```
User
  ↓
CLI Parser (tagfs.py)
  ↓
Handler Functions (_add_tags, _tag_resource, etc.)
  ↓
TagfsUtilities.TagfsTagHandlerUtilities
  ├→ Normalize URL paths
  ├→ Parse hierarchical tags
  └→ Delegate to TagService
      ↓
    TagService
      ├→ DatabaseManager (orchestrates storage)
      │   ├→ SQLiteHandler (TAGS, RESOURCES, ID_SEQUENCES)
      │   └→ RDFHandler (skos:broader + htfs:hasTag)
      └→ QueryEvaluator (for complex expressions)
          └→ AST → SPARQL compilation against RDF graph
          ↓
      Query results map resource URIs → SQLite URLs
      ↑
      RDF graph loaded/written by RDFHandler
```

---

## Core Components

### 1. **CLI Layer (tagfs.py)**

The CLI exposes commands for initialization, tag/resource management, expression queries, and filesystem diagnostics. Each handler obtains a `TagfsTagHandlerUtilities` instance, normalizes paths, parses hierarchical inputs, and delegates the heavy work to `TagService`.
---

### 2. **Utilities Layer (TagfsUtilities.py)**

`TagfsTagHandlerUtilities` maintains the tagfs boundary cache, normalizes resource URLs relative to that boundary, parses hierarchical tag syntax such as `Project/Alpha/Reports`, and exposes helpers like `add_tags`, `tag_resource`, `get_resources_by_tag_expr`, `link_tags`, and `is_resource_tracked`. It keeps the CLI boundary-aware while relying on `TagService` for persistence.
---

### 3. **High-Level Service Layer (TagService.py)**

`TagService` is the facade used by CLI utilities. It instantiates `DatabaseManager`, exposes CRUD operations for tags and resources, auto-creates missing tags when adding resource tags, computes closures, and exposes `flush`/`close` to persist RDF only when needed.
---

### 4. **Storage Coordinator & Handlers**

`DatabaseManager` orchestrates the SQLite and RDF storage layers. It initializes `.tagfs.db` (`TAGS`, `RESOURCES`, `ID_SEQUENCES`), routes identifier lookups to SQLite, and routes hierarchy/resource-tag management to `RDFHandler`. Bulk helpers such as `add_resource_tags`, `link_tag_to_parent`, and `get_resources_by_tag` combine lookups with RDF link creation, while `flush()`/`close()` serialize RDF only when modifications occur.

#### SQLite Handler

- Maintains the relational tables: `TAGS (ID, TAGNAME)`, `RESOURCES (ID, URL)`, and `ID_SEQUENCES`
- Ensures deterministic numeric identifiers for tags and resources so RDF URIs (`htfs:tag_{id}`, `htfs:resource_{id}`) stay stable
- Provides fast helper methods for inserting, renaming, moving, and deleting entries
- Exposes monotonic ID generation that keeps SQLite and RDF in sync

#### RDF Handler

- Stores hierarchical relationships (`skos:broader`) and resource assignments (`htfs:hasTag`) in `.tagfs.ttl`
- Lazily loads the `rdflib.Graph`, tracks a dirty flag, and serializes only on demand
- Provides helpers like `add_tag_link`, `remove_tag_link`, `get_tag_closure_ids`, `add_resource_tag_link`, and `get_resources_by_tag_ids`
- QueryEvaluator executes SPARQL on this graph and maps each `htfs:resource_{id}` URI back to SQLite for the final normalized URL list
---

### 5. **Query Engine (QueryEvaluator.py)**

Tokenizes tag expressions, builds an AST, and compiles SPARQL clauses that traverse `htfs:hasTag` and `skos:broader*`. After the RDF query returns `htfs:resource_{id}` URIs, the ASTEvaluator extracts each numeric ID and asks SQLite for the normalized URL list so the CLI receives filesystem paths instead of RDF resources.
---

### 6. **Filesystem Integration (tagfs_inotify_daemon.py)**

The optional daemon monitors the tagfs boundary via `inotify.adapters.InotifyTree`. It captures `IN_MOVED_FROM`/`IN_MOVED_TO` pairs, uses `TagfsUtilities.move_resource()` to normalize the paths, and relies on `TagService` to update SQLite/RDF so resource IDs and their tag links follow the filesystem move.
---

### 7. **Data Migration (migrate_sql_to_rdf.py)**

Rebuilds `.tagfs.ttl` from legacy SQLite tables (`TAGS`, `TAGLINKS`, `RESOURCES`, `RESOURCELINKS`) while preserving the `ID_SEQUENCES`. The migration inserts the same `skos:broader` and `htfs:hasTag` triples consumed by `RDFHandler`, ensuring the new split storage can be reconstructed from older exports.
---

## Data Model & Ontology

### RDF Ontology Definition

#### Namespaces:
```turtle
@prefix htfs: <http://htfs.example.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

#### Classes:

**skos:Concept** (from SKOS vocabulary)
- Represents tags in a controlled vocabulary
- Supports hierarchical relationships

**htfs:Resource**
- Represents tracked files and directories
- Contains filesystem metadata

#### Properties:

| Property | Domain | Range | Purpose |
|----------|--------|-------|---------|
| `skos:prefLabel` | `skos:Concept` | `xsd:string` | Tag display name |
| `skos:broader` | `skos:Concept` | `skos:Concept` | Parent tag (inverse: `skos:narrower`) |
| `htfs:id` | `skos:Concept` ∪ `htfs:Resource` | `xsd:integer` | Numeric identifier |
| `htfs:url` | `htfs:Resource` | `xsd:string` | Filesystem path (relative to boundary) |
| `htfs:hasTag` | `htfs:Resource` | `skos:Concept` | Tag assignment |
| `htfs:maxTagId` | `htfs:meta` | `xsd:integer` | Metadata: highest tag ID |
| `htfs:maxResourceId` | `htfs:meta` | `xsd:integer` | Metadata: highest resource ID |

### Example RDF Graph

```turtle
@prefix htfs: <http://htfs.example.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

# Tags
htfs:tag_Project a skos:Concept ;
    skos:prefLabel "Project" ;
    htfs:id 1 .

htfs:tag_Alpha a skos:Concept ;
    skos:prefLabel "Alpha" ;
    skos:broader htfs:tag_Project ;
    htfs:id 2 .

htfs:tag_Reports a skos:Concept ;
    skos:prefLabel "Reports" ;
    skos:broader htfs:tag_Alpha ;
    htfs:id 3 .

htfs:tag_Research a skos:Concept ;
    skos:prefLabel "Research" ;
    htfs:id 4 .

# Resources
htfs:resource_1 a htfs:Resource ;
    htfs:url "reports/alpha_q1_2026.pdf" ;
    htfs:id 1 ;
    htfs:hasTag htfs:tag_Reports ;
    htfs:hasTag htfs:tag_Research .

htfs:resource_2 a htfs:Resource ;
    htfs:url "reports/beta_draft.pdf" ;
    htfs:id 2 ;
    htfs:hasTag htfs:tag_Reports .

# Metadata
htfs:meta htfs:maxTagId 4 ;
    htfs:maxResourceId 2 .
```

### Tag Hierarchy Semantics

**Broader/Narrower Relationships**:
- `skos:broader` indicates a parent relationship
- `skos:narrower` (inverse) indicates child relationship
- Used for transitive closure queries with `skos:broader+`

**Hierarchy Example**:
```
Project (1)
  ├── Alpha (2)
  │     └── Reports (3)
  └── Beta (5)
        └── Planning (6)

Research (4)  [Independent branch]
```

**Query: Find all resources tagged with "Project"**
- Returns resources directly tagged with `Project`
- Returns resources tagged with `Alpha`, `Beta`, `Reports`, or `Planning` (descendants)
- Due to transitive closure: `skos:broader*`

---

## API & Interfaces

### Python API

#### TagService Interface
```python
from TagService import TagService

# Initialize
ts = TagService(".tagfs.ttl")
ts.initialize()

# Tag operations
ts.add_tag("Project")
tag_id = ts.get_tag_id("Project")
ts.link_tag("Alpha", "Project")  # Alpha is child of Project

# Resource operations
res_id = ts.add_resource("reports/result.pdf")
ts.add_resource_tags("reports/result.pdf", ["Reports", "Research"])
tags = ts.get_resource_tags("reports/result.pdf")
resources = ts.get_resources_by_tag(["Project"])
```

#### QueryEvaluator Interface
```python
from QueryEvaluator import QueryEvaluator

qe = QueryEvaluator(ts)
results = qe.evaluate("(proj1|proj2)&research&~draft")
# Returns list of resource URLs matching expression
```

#### Utilities Interface
```python
from TagfsUtilities import TagfsTagHandlerUtilities, get_tag_fs_boundary

# Auto-detect tagfs boundary
boundary = get_tag_fs_boundary()

# High-level utilities
utils = TagfsTagHandlerUtilities(boundary)
utils.add_tags(["Project/Alpha/Reports"])  # Hierarchical create
resources = utils.get_resources_by_tag_expr("(proj1|proj2)&research")
```

### Command-Line Interface

```bash
# Initialize
tagfs init

# Tag management
tagfs addtags Project Alpha Beta
tagfs addtags "Project/Alpha/Reports"  # Creates hierarchy
tagfs linktags Research Project
tagfs lstags
tagfs renametag Alpha Alpha_v1

# Resource management
tagfs addresource /data/file.pdf
tagfs tagresource /data/file.pdf Reports Research
tagfs getresourcetags /data/file.pdf
tagfs lsresources "(proj1|proj2)&research"

# Filesystem operations
tagfs mvresource /data/file.pdf /data/new/file.pdf
tagfs rmresource /data/file.pdf

# Utilities
tagfs getboundary
tagfs help
```

---

## Query Processing Pipeline

### End-to-End Query Execution

#### Example: `lsresources "(proj1|proj2)&research&~draft"`

**Step 1: Tokenization** (QueryEvaluator.Tokenizer)
```
Input:  "(proj1|proj2)&research&~draft"
Output: ['(', 'proj1', '|', 'proj2', ')', '&', 'research', '&', '~', 'draft']
```

**Step 2: Parsing** (QueryEvaluator.Parser)
```
Output: AST
        &
       / \
      &   ~
     / \   \
    |   research   draft
   / \
proj1 proj2
```

**Step 3: SPARQL Compilation** (QueryEvaluator.ASTEvaluator)
```
_compile(AST) emits clauses that match
├─ ?resource htfs:hasTag ?tag1 .
│  ?tag1 skos:broader* htfs:tag_proj1 .
├─ UNION { ?resource htfs:hasTag ?tag2 .
│          ?tag2 skos:broader* htfs:tag_proj2 . }
├─ ?resource htfs:hasTag ?tag3 .
│  ?tag3 skos:broader* htfs:tag_research .
└─ FILTER NOT EXISTS { ?resource htfs:hasTag ?tag4 .
                       ?tag4 skos:broader* htfs:tag_draft . }
```

**Step 4: Query Execution**
RDFHandler executes the SPARQL against the in-memory graph and returns `htfs:resource_{id}` URIs. ASTEvaluator extracts the numeric IDs and queries SQLite (`DatabaseManager`) to fetch the normalized `URL` strings.

**Step 5: Result Processing** (TagfsUtilities)
- Convert normalized URLs to absolute paths
- Apply tagfs boundary
- Return filesystem paths to the CLI caller

---

## Storage & Persistence

### Physical Files

- `.tagfs.db` (SQLite): Stores `TAGS (ID, TAGNAME)`, `RESOURCES (ID, URL)`, and `ID_SEQUENCES`. Every tag or resource name maps to a deterministic numeric ID, ensuring the RDF graph can refer to them without repeated lookups. This database supports fast name↔ID lookups, renames, and moves.
- `.tagfs.ttl` (RDF/Turtle): Stores the semantic relationships (`skos:broader` for hierarchy, `htfs:hasTag` for resource assignments) between the numeric IDs as `htfs:tag_{id}` and `htfs:resource_{id}` URIs. The RDF graph is human-readable, Git-friendly, and compatible with `rdflib`.

### Serialization & Consistency

- `RDFHandler` lazily loads `.tagfs.ttl`, marks the graph dirty on mutations, and serializes only during `close()`/`flush()` or when explicitly triggered. SQLite commits immediately, while RDF writes are batched for performance.
- `ID_SEQUENCES` in SQLite guarantee that tag/resource IDs never collide, even when migration scripts rebuild the RDF graph from scratch.
- The split model keeps high-throughput lookups in SQL and relationship/closure logic in RDF, avoiding large graphs by only storing links instead of repeated metadata.

### Backup & Recovery

- Version control both `.tagfs.db` and `.tagfs.ttl` together so the hybrid model can be restored.
- Use `migrate_sql_to_rdf.py` if you need to rebuild RDF from SQLite snapshots or recover from corruption.

---

## Design Patterns

### 1. **Repository Pattern**

**Implementation**: SQLiteHandler + RDFHandler coordinated by DatabaseManager

**Benefit**: Splits fast name↔ID lookups (SQLite) from graph relationships (RDF) while exposing a unified API.

**Structure**:
```python
class DatabaseManager:
    def __init__(self, boundary):
        self.sqlite = SQLiteHandler(...)
        self.rdf = RDFHandler(...)
```

### 2. **Facade Pattern**

**Implementation**: TagService

**Benefit**: Simplifies API by combining the storage and query layers behind `DatabaseManager`.

```python
class TagService:
    def __init__(self, boundary):
        self.db = DatabaseManager(boundary)
        self.db.connect()
```

### 3. **Compiler Pattern**

**Implementation**: QueryEvaluator.ASTEvaluator

**Benefit**: Parses user input → intermediate representation → executable query

```
Expression → Tokenizer → Parser → AST → Compiler → SPARQL → Executor
```

### 4. **Command Pattern**

**Implementation**: tagfs.py command handlers

**Benefit**: Decouples command parsing from execution

```python
COMMANDS = {
    'init': _init_tag_fs,
    'addtags': _add_tags,
    'lsresources': _get_resources_by_tag_expr,
    # ...
}

def tagfs(args):
    handler = COMMANDS[args.command]
    return handler(args)
```

### 5. **Observer Pattern** (Optional)

**Implementation**: tagfs_inotify_daemon.py

**Benefit**: Monitors filesystem and reacts to changes

```
FileSystem Events → Inotify → Event Queue → Handler → TagfsUtilities
```

### 6. **Context Manager Pattern**

**Implementation**: DatabaseManager / RDFHandler

**Benefit**: Automatic connection lifecycle management and RDF serialization.

```python
with DatabaseManager(boundary) as db:
    db.add_resource("/data/file")
    db.flush()
```

---

## Use Cases & Workflows

### Use Case 1: Research Paper Organization

**Scenario**: Organizing research papers across overlapping categories

**Tags Hierarchy**:
```
Science/
  ├─ Biology/
  │    ├─ Genetics/
  │    └─ Ecology/
  ├─ Physics/
  │    └─ Quantum/
  └─ Chemistry/

Status/
  ├─ ToRead
  ├─ Reading
  └─ Completed

Year/
  ├─ 2024
  ├─ 2025
  └─ 2026
```

**Operations**:

```bash
# Setup
tagfs init
tagfs addtags "Science/Biology/Genetics"
tagfs addtags "Science/Physics/Quantum"
tagfs addtags "Status/ToRead" "Status/Reading" "Status/Completed"
tagfs addtags "Year/2024" "Year/2025" "Year/2026"

# Add resources
tagfs addresource ~/papers/crispr_2025.pdf
tagfs addresource ~/papers/quantum_entanglement_2024.pdf

# Tag resources
tagfs tagresource ~/papers/crispr_2025.pdf Genetics Reading 2025
tagfs tagresource ~/papers/quantum_entanglement_2024.pdf Quantum ToRead 2024

# Queries
tagfs lsresources "Science&2025"                    # Papers in 2025 under Science
tagfs lsresources "(Genetics|Quantum)&~ToRead"     # Physics/Biology papers being read/completed
tagfs lsresources "Science&(Reading|Completed)"    # Currently reading/read science papers
```

### Use Case 2: Project File Management

**Scenario**: Managing files for overlapping projects with different phases

**Tags Hierarchy**:
```
Project/
  ├─ ProjectAlpha
  │    ├─ Design
  │    ├─ Development
  │    └─ Testing
  └─ ProjectBeta
       ├─ Planning
       └─ Implementation

Visibility/
  ├─ Internal
  └─ Client

Status/
  ├─ Active
  ├─ OnHold
  └─ Archived
```

**Operations**:

```bash
# Setup
tagfs addtags "Project/ProjectAlpha/Design"
tagfs addtags "Project/ProjectAlpha/Development"
tagfs addtags "Project/ProjectBeta/Planning"

tagfs linktags Visibility/Internal Project
tagfs linktags Visibility/Client Project

# Tagging files
tagfs tagresource ./docs/alpha_spec.pdf ProjectAlpha Design Internal Active
tagfs tagresource ./code/beta_prototype.py ProjectBeta Planning OnHold

# Queries
tagfs lsresources "Project&Active"                     # All active project files
tagfs lsresources "(ProjectAlpha|ProjectBeta)&~OnHold" # Files from both projects, not on hold
tagfs lsresources "ProjectAlpha&(Design|Development)"  # Alpha design and dev files
```

### Use Case 3: Automatic Filesystem Event Tracking

**Scenario**: Daemon-based automatic tagging on file moves

```bash
# Start daemon in background
tagfs_inotify_daemon.py /my/data &

# Manually tag once
tagfs addresource /my/data/important.pdf
tagfs tagresource /my/data/important.pdf ImportantDocs

# Move file - daemon automatically updates URL
mv /my/data/important.pdf /my/data/archive/important.pdf
# Database updated to: archive/important.pdf

# Move directory - all contained resources updated
mv /my/data/project_files/ /my/data/completed/project_files/
# All resources with "project_files/*" paths updated accordingly
```

---

## Performance Considerations

### Query Performance

**Factors Affecting Speed**:

1. **Graph Size**: Number of triples
   - Linear growth with tags and resources
   - Typically manageable for < 100k resources

2. **Query Complexity**: Expression structure
   - AND/OR clauses multiply SPARQL patterns
   - Transitive closure (`skos:broader+`) may be expensive

3. **Materialization vs. Computation**:
   - Currently: Computed on-the-fly (no caching)
   - Could optimize: Pre-compute tag closures

### Optimization Techniques

**1. ID-based Lookups**:
- Numeric IDs used internally for efficiency
- SPARQL filters by `htfs:id` faster than string comparisons

**2. SPARQL UNION Patterns**:
- OR operations use UNION (standard SPARQL optimization)
- Allows query planner to optimize each branch

**3. Graph Indexing**:
- rdflib maintains indexes on predicates
- `skos:broader`, `htfs:hasTag` heavily indexed

**4. Future Optimizations**:
- Materialized tag closure table (computed periodically)
- Prefix indexing on URLs (for `CONTAINS` queries)
- Query result caching

### Scalability Limits

| Metric | Capacity | Notes |
|--------|----------|-------|
| Tags | 10k-100k | Manageable with efficient SPARQL |
| Resources | 1M+ | Limited by RDF triple count |
| Relationships | N/A | Graph remains sparse (DAG structure) |
| Query Response | < 1s | For typical 100-1000 resource result sets |

**Scaling Strategy**:
- Current design suitable for personal/team workflows
- For enterprise scale (millions): Consider RDF triple stores (Virtuoso, Fuseki)

---

## Future Extensions

### 1. **Web Service API**

Expose functionality over REST/GraphQL:

```
POST /api/tags
GET  /api/tags/{id}
POST /api/resources/{id}/tags
GET  /api/search?expr=(proj1|proj2)&status=active
```

### 2. **Tag Inference & Auto-tagging**

- Machine learning on file content (NLP for documents)
- Automatic suggestions based on naming patterns
- Template-based auto-tagging on directory structure

### 3. **Advanced Query Language**

- Temporal queries: `tag@date(YYYY-MM-DD)`
- Numeric ranges: `year:[2020..2025]`
- Metadata filters: `size:>1MB&mimetype:PDF`

### 4. **Visualization & Reporting**

- Tag hierarchy graph visualization
- Resource distribution by tag
- Query result statistics

### 5. **Multi-User & Concurrency**

- Distributed metadata store (Git-based)
- Conflict resolution for tag changes
- Role-based access control

### 6. **External Integration**

- Email client plugin (tag received attachments)
- File manager integration (context menu tagging)
- Document management system connector
- Backup service metadata tagging

### 7. **Performance Scaling**

- Triple store backend (RDF DB)
- Query caching layer
- Materialized views for common queries
- Full-text search integration

### 8. **Enhanced Metadata**

- Tag descriptions and documentation
- Resource annotations (comments)
- Tag versioning and change history
- Resource access patterns and metrics

---

## Conclusion

HTFS represents an innovative approach to filesystem organization by **decoupling taxonomy from hierarchy**. By leveraging RDF and SPARQL, it provides:

✅ **Flexibility**: Multiple categorization schemes simultaneously
✅ **Power**: Complex queries through boolean expressions
✅ **Simplicity**: Intuitive CLI for everyday usage
✅ **Portability**: Text-based storage, Git-friendly
✅ **Extensibility**: Ontology-based design enables future enhancements

The system balances **semantic richness** (RDF/SKOS ontology) with **practical usability** (CLI interface), making it suitable for researchers, data professionals, and anyone needing advanced file organization.

---

## Appendices

### A. Configuration Reference

**Environment Variables**:
- `TAGFS_DB`: Override default `.tagfs.ttl` location

### B. Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (database not initialized, invalid arguments, etc.) |

### C. Dependencies

- **rdflib** (>= 6.0): RDF graph management
- **inotify** (optional): Filesystem event monitoring (Linux only)

### D. File Formats

**Supported**:
- RDF Turtle (`.ttl`)

**Legacy** (via migration):
- SQLite (`.db`) → converted to RDF

### E. SPARQL Vocabulary Reference

**SKOS (Simple Knowledge Organization System)**:
- `skos:Concept`: Tagged concept/category
- `skos:prefLabel`: Preferred display label
- `skos:broader`: Parent concept
- `skos:narrower`: Child concept (inverse)

**HTFS Custom Vocabulary**:
- `htfs:Resource`: Tracked file/directory
- `htfs:id`: Numeric identifier
- `htfs:url`: File path
- `htfs:hasTag`: Tag assignment
- `htfs:maxTagId`: Metadata counter
- `htfs:maxResourceId`: Metadata counter

---

**Document Generated**: March 2026
**System Version**: HTFS-SPARQL v1.0
**For Updates & Issues**: See repository documentation
